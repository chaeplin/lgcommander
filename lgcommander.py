#!/usr/bin/env python2
# encoding: utf-8
# code from https://github.com/ubaransel/lgcommander
# code from https://github.com/ypid/lgcommander

import re
import logging
import socket
import sys
import xml.etree.ElementTree as etree
import httplib
from cStringIO import StringIO

lgtv = {}
headers = {"Content-Type": "application/atom+xml"}
lgtv["pairingKey"] = "111111"

def getip():
    strngtoXmit =   'M-SEARCH * HTTP/1.1' + '\r\n' + \
                    'HOST: 239.255.255.250:1900'  + '\r\n' + \
                    'MAN: "ssdp:discover"'  + '\r\n' + \
                    'MX: 2'  + '\r\n' + \
                    'ST: urn:schemas-upnp-org:device:MediaRenderer:1'  + '\r\n' +  '\r\n'

    bytestoXmit = strngtoXmit.encode()
    sock = socket.socket( socket.AF_INET, socket.SOCK_DGRAM )
    sock.settimeout(3)
    found = False
    gotstr = 'notyet'
    i = 0
    ipaddress = None
    sock.sendto( bytestoXmit,  ('239.255.255.250', 1900 ) )
    while not found and i <= 5 and gotstr == 'notyet':
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
        raise socket.error("Lg TV not found.") 
    logging.info("Using device: {} over transport protocol: {}/tcp".format(ipaddress, port))
    return ipaddress


def getSessionid():
    if not lgtv["pairingKey"]:
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
        raise Exception("Could not get Session Id: {}".format(_session_id))
    return _session_id

def getstatus():
    conn = httplib.HTTPConnection(lgtv["ipaddress"], port=8080)
    conn.request("GET", "/udap/api/data?target=cur_channel", headers=headers)
    httpResponse = conn.getresponse()
    if httpResponse.reason != 'OK':
        return None
    tree = etree.XML(httpResponse.read())

    for data in tree.findall('data'):
        inputSourceName = data.find('inputSourceName').text
        labelName = data.find('labelName').text

    print inputSourceName, labelName

#  inputSourceName and labelName are updated after using remote app. 
#   
#<?xml version="1.0" encoding="utf-8"?>
#<envelope>
#<ROAPError>200</ROAPError>
#<ROAPErrorDetail>OK</ROAPErrorDetail>
#<data>
#    <chtype>satellite</chtype>
#    <sourceIndex>8</sourceIndex>
#    <physicalNum>65535</physicalNum>
#    <major>65520</major>
#    <displayMajor>65520</displayMajor>
#    <minor>65520</minor>
#    <displayMinor>-16</displayMinor>
#    <chname></chname>
#    <progName></progName>
#    <audioCh>0</audioCh>
#    <inputSourceName>HDMI1</inputSourceName>
#    <inputSourceType>1</inputSourceType>
#    <labelName>IPTV</labelName>
#    <inputSourceIdx>4</inputSourceIdx>
#</data>
#</envelope>

# /udap/api/data?target=screen_image

logging.basicConfig(
    format='# %(levelname)s: %(message)s',
    level=logging.DEBUG,
    # level=logging.INFO,
)

lgtv["ipaddress"] = getip()
theSessionid = getSessionid()
while theSessionid == "Unauthorized" :
    getPairingKey()
    theSessionid = getSessionid()

if len(theSessionid) < 8 : sys.exit("Could not get Session Id: " + theSessionid)

lgtv["session"] = theSessionid

getstatus()
