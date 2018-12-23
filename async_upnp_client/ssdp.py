# -*- coding: utf-8 -*-
"""SSPD protocol handler."""

import email
import logging

from datetime import datetime


SSDP_TARGET = ('239.255.255.250', 1900)
SSDP_ST_ALL = 'ssdp:all'
SSDP_ST_ROOTDEVICE = 'upnp:rootdevice'
SSDP_MX = 4

SSDP_ALIVE = 'ssdp:alive'
SSDP_UPDATE = 'ssdp:update'
SSDP_BYEBYE = 'ssdp:byebye'


_LOGGER = logging.getLogger(__name__)
_LOGGER_TRAFFIC = logging.getLogger("async_upnp_client.traffic")


def build_ssdp_search_packet(ssdp_target: str, ssdp_mx: int, ssdp_st: str):
    """Construct a SSDP packet."""
    return 'M-SEARCH * HTTP/1.1\r\n' \
           'HOST:{target}:{port}\r\n' \
           'MAN:"ssdp:discover"\r\n' \
           'MX:{mx}\r\n' \
           'ST:{st}\r\n' \
           '\r\n'.format(target=ssdp_target[0], port=ssdp_target[1],
                         mx=ssdp_mx, st=ssdp_st).encode()


def is_valid_ssdp_packet(data):
    """Check if data is a valid and decodable packet."""
    return data and \
        b'\n' in data and \
        (data.startswith(b'NOTIFY * HTTP/1.1') or
         data.startswith(b'M-SEARCH * HTTP/1.1') or
         data.startswith(b'HTTP/1.1 200 OK'))


def decode_ssdp_packet(data, addr):
    """Decode a message."""
    lines = data.split(b'\n')

    # request_line
    request_line = lines[0].strip()

    # parse headers
    header_lines = b'\n'.join(lines[1:])
    headers = email.message_from_bytes(header_lines)

    # own data
    headers['_timestamp'] = datetime.now()
    headers['_address'] = addr
    if 'usn' in headers and 'uuid:' in headers['usn']:
        parts = headers['usn'].split('::')
        if len(parts) > 1:
            headers['_udn'] = parts[0] if 'uuid:' in parts[0] else parts[1]
        else:
            headers['_udn'] = parts[0]

    return request_line, headers


class SsdpProtocol:
    """SSDP Protocol."""

    def __init__(self, loop, on_connect=None, on_data=None):
        """Initializer."""
        self.loop = loop
        self.on_connect = on_connect
        self.on_data = on_data

        self.on_con_lost = loop.create_future()
        self.transport = None

    def connection_made(self, transport):
        """Handle connection made."""
        self.transport = transport

        if self.on_connect:
            callback = self.on_connect(transport)
            self.loop.create_task(callback)

    def datagram_received(self, data, addr):
        """Handle a discovery-response."""
        _LOGGER_TRAFFIC.debug('Received packet from %s:\n%s', addr, data)

        if is_valid_ssdp_packet(data) and self.on_data:
            request, headers = decode_ssdp_packet(data, addr)
            callback = self.on_data(request, headers)
            self.loop.create_task(callback)

    def error_received(self, exc):
        """Handle an error."""
        # pylint: disable=no-self-use
        _LOGGER.debug('Received error: %s', exc)

    def connection_lost(self, exc):
        """Handle connection lost."""
