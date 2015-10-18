#!/usr/bin/python
# encoding: utf-8
# code from https://github.com/ubaransel/lgcommander
# code from https://github.com/ypid/lgcommander

import re
import logging
import socket
import sys
import time
import xml.etree.ElementTree as etree
import httplib
import urllib2
from PIL import Image
import pyocr
import pyocr.builders
import StringIO
from pymemcache.client.base import Client

lgtv = {}
lgtvchlist = {}

headers = {"Content-Type": "application/atom+xml"}
lgtv["pairingKey"] = "914850"
lgtv["ipaddress"]  = ""
lgtv["toch"]  = "HDMIZ"


def getip():
    strngtoXmit =   'M-SEARCH * HTTP/1.1' + '\r\n' + \
                    'HOST: 239.255.255.250:1900'  + '\r\n' + \
                    'MAN: "ssdp:discover"'  + '\r\n' + \
                    'MX: 2'  + '\r\n' + \
                    'ST: urn:schemas-upnp-org:device:MediaRenderer:1'  + '\r\n' +  '\r\n'

    bytestoXmit = strngtoXmit.encode()
    sock = socket.socket( socket.AF_INET, socket.SOCK_DGRAM )
    sock.settimeout(1)
    found = False
    gotstr = 'notyet'
    i = 0
    ipaddress = None
    sock.sendto( bytestoXmit,  ('239.255.255.250', 1900 ) )
    while not found and i <= 2 and gotstr == 'notyet':
        try:
            gotbytes, addressport = sock.recvfrom(512)
            gotstr = gotbytes.decode()
        except:
            i += 1
            sock.sendto( bytestoXmit, ( '239.255.255.250', 1900 ) )
        if re.search('LG', gotstr):
            logging.debug("Returned: {}".format(gotstr))

            ipaddress, port = addressport
            logging.debug("Found device: {}".format(ipaddress))

            found = True
        else:
            gotstr = 'notyet'
        i += 1
    sock.close()
    if not found:
        return None
    logging.info("Using device: {} over transport protocol: {}/tcp".format(ipaddress, port))
    return ipaddress


def getSessionid():
    if not lgtv["pairingKey"]:
        return None
    if not lgtv["ipaddress"]:
        return None

    conn = httplib.HTTPConnection(lgtv["ipaddress"], port=8080)
    pairCmd = "<?xml version=\"1.0\" encoding=\"utf-8\"?><auth><type>AuthReq</type><value>" \
            + lgtv["pairingKey"] + "</value></auth>"
    conn.request("POST", "/roap/api/auth", pairCmd, headers=headers)
    httpResponse = conn.getresponse()
    if httpResponse.reason != 'OK':
        return None
    tree = etree.XML(httpResponse.read())
    _session_id = tree.find('session').text
    logging.debug("Session ID is {}".format(_session_id))
    if len(_session_id) < 8:
        sys.exit(1)
    return _session_id

#   /udap/api/data?target=cur_channel are updated after selecting input source using remote app.
#   so useless after power up  
#   <?xml version="1.0" encoding="utf-8"?>
#   <envelope>
#   <ROAPError>200</ROAPError>
#   <ROAPErrorDetail>OK</ROAPErrorDetail>
#   <data>
#       <chtype>satellite</chtype>
#       <sourceIndex>8</sourceIndex>
#       <physicalNum>65535</physicalNum>
#       <major>65520</major>
#       <displayMajor>65520</displayMajor>
#       <minor>65520</minor>
#       <displayMinor>-16</displayMinor>
#       <chname></chname>
#       <progName></progName>
#       <audioCh>0</audioCh>
#       <inputSourceName>HDMI1</inputSourceName>
#       <inputSourceType>1</inputSourceType>
#       <labelName>IPTV</labelName>
#       <inputSourceIdx>4</inputSourceIdx>
#   </data>
#   </envelope>
#   
#   def getstatus():
#       conn = httplib.HTTPConnection(lgtv["ipaddress"], port=8080)
#       conn.request("GET", "/udap/api/data?target=cur_channel", headers=headers)
#       httpResponse = conn.getresponse()
#       if httpResponse.reason != 'OK':
#           return None
#   
#       htmlout = httpResponse.read()
#       print htmlout
#   
#       tree = etree.XML(htmlout)
#       for data in tree.findall('data'):
#           inputSourceIdx  = data.find('inputSourceIdx').text
#           inputSourceName = data.find('inputSourceName').text
#           labelName = data.find('labelName').text
#   
#       print inputSourceIdx, inputSourceName, labelName


def handleCommand(cmdcode):
    conn = httplib.HTTPConnection( lgtv["ipaddress"], port=8080)
    cmdText = "<?xml version=\"1.0\" encoding=\"utf-8\"?><command>" \
                + "<name>HandleKeyInput</name><value>" \
                + cmdcode \
                + "</value></command>"
    conn.request("POST", "/roap/api/command", cmdText, headers=headers)
    httpResponse = conn.getresponse()
    if httpResponse.reason != 'OK':
        return None
    
    return True

def getscreenimage():
    ch = ''
    ap = ''

    conn = httplib.HTTPConnection(lgtv["ipaddress"], port=8080)
    conn.request("GET", "/udap/api/data?target=screen_image")
    httpResponse = conn.getresponse()
    if httpResponse.reason != 'OK':
        return None

    htmlout = httpResponse.read()
    im = Image.open(StringIO.StringIO(htmlout)).convert('RGB')

    # ocr
    tools = pyocr.get_available_tools()
    if len(tools) == 0:
        print("No OCR tool found")
        sys.exit(1)
    tool = tools[0]
    lang = 'eng'

    # crop and ocr
    im_crop = {}
    for x in range(1, 5):
        box = ((65 + (140 * (x -1))), 394, (65 + 120 + (140 * (x -1))), 416)
        im_crop[x] = im.crop(box)
        ocrtxt = tool.image_to_string(im_crop[x], lang=lang, builder=pyocr.builders.TextBuilder())
        lgtvchlist[x] = ocrtxt
        if ocrtxt == lgtv["toch"]:
            ap = x

    # get ch
    for x in range(1, 5):
        r, g, b = im.getpixel(((130 * x), 430))
        if r < 180 and g < 50 and b < 60:
            ch = x
            break

    if ch:
        return ch, ap
    else:
        return None

#---------------------------
def changeinout(cur_ch, to_ch):
    if cur_ch > to_ch:
        cmd = '14'
    else:
        cmd = '15'

    for x in range(0, abs(cur_ch - to_ch)):
        handleCommand(cmd)
        time.sleep(1)

    handleCommand("20")
      

#----------------------------
def getCHandHDMI2():
    lgtv["ipaddress"] = getip()
    if not lgtv["ipaddress"]:
        logging.debug("TV not found")
        sys.exit(1)

    theSessionid = getSessionid()
    while theSessionid == "Unauthorized" :
        getPairingKey()
        theSessionid = getSessionid()

    lgtv["session"] = theSessionid

    # exit any current menu in screen
    handleCommand("412")
    time.sleep(1)

    # check current input source no
    if handleCommand("47"):
        time.sleep(4)
        m, n = getscreenimage()
        return m, n

#------------------------
#logging.basicConfig(
#    format='# %(levelname)s: %(message)s',
#    level=logging.DEBUG,
#)

client = Client(('127.0.0.1', 11211))

try:
        result = client.get('appletv')
        if result:
            sys.exit("time is not passed")
        else:
            print ("appletv is on")
            # get current channel and change input to HDMI2
            # tv should be on
            m, n = getCHandHDMI2()
            if m != n:
                changeinout(m, n)
            else:
                handleCommand("20")
            client.set('appletv', 'true', 60) 

except Exception, e:
        print e.__doc__
        print e.message      
        sys.exit(1)
