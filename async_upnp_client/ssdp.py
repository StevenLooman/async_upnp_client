# -*- coding: utf-8 -*-
"""SSPD protocol handler."""

import email
import logging

from asyncio import BaseProtocol
from datetime import datetime
from typing import Tuple

from async_upnp_client.utils import CaseInsensitiveDict


SSDP_TARGET = ('239.255.255.250', 1900)
SSDP_ST_ALL = 'ssdp:all'
SSDP_ST_ROOTDEVICE = 'upnp:rootdevice'
SSDP_MX = 4

SSDP_ALIVE = 'ssdp:alive'
SSDP_UPDATE = 'ssdp:update'
SSDP_BYEBYE = 'ssdp:byebye'


_LOGGER = logging.getLogger(__name__)
_LOGGER_TRAFFIC = logging.getLogger("async_upnp_client.traffic")


def build_ssdp_search_packet(ssdp_target: Tuple[str, int], ssdp_mx: int, ssdp_st: str) -> bytes:
    """Construct a SSDP packet."""
    return 'M-SEARCH * HTTP/1.1\r\n' \
           'HOST:{target}:{port}\r\n' \
           'MAN:"ssdp:discover"\r\n' \
           'MX:{mx}\r\n' \
           'ST:{st}\r\n' \
           '\r\n'.format(target=ssdp_target[0], port=ssdp_target[1],
                         mx=ssdp_mx, st=ssdp_st).encode()


def is_valid_ssdp_packet(data: bytes) -> bool:
    """Check if data is a valid and decodable packet."""
    return bool(data) and \
        b'\n' in data and \
        (data.startswith(b'NOTIFY * HTTP/1.1') or
         data.startswith(b'M-SEARCH * HTTP/1.1') or
         data.startswith(b'HTTP/1.1 200 OK'))


def decode_ssdp_packet(data: bytes, addr: str) -> Tuple[str, CaseInsensitiveDict]:
    """Decode a message."""
    lines = data.split(b'\n')

    # request_line
    request_line = lines[0].strip().decode()

    # parse headers
    header_lines = b'\n'.join(lines[1:])
    email_headers = email.message_from_bytes(header_lines)
    headers = CaseInsensitiveDict(**dict(email_headers.items()))

    # own data
    headers['_timestamp'] = datetime.now()
    headers['_address'] = addr
    if 'usn' in headers and 'uuid:' in headers['usn']:
        parts = str(headers['usn']).split('::')
        if len(parts) > 1:
            headers['_udn'] = parts[0] if 'uuid:' in parts[0] else parts[1]
        else:
            headers['_udn'] = parts[0]

    return request_line, headers


class SsdpProtocol(BaseProtocol):
    """SSDP Protocol."""

    def __init__(self, loop, on_connect=None, on_data=None) -> None:
        """Initializer."""
        self.loop = loop
        self.on_connect = on_connect
        self.on_data = on_data

        self.on_con_lost = loop.create_future()
        self.transport = None

    def connection_made(self, transport) -> None:
        """Handle connection made."""
        self.transport = transport

        if self.on_connect:
            callback = self.on_connect(transport)
            self.loop.create_task(callback)

    def datagram_received(self, data, addr) -> None:
        """Handle a discovery-response."""
        _LOGGER_TRAFFIC.debug('Received packet from %s:\n%s', addr, data)

        address = '{}:{}'.format(*addr)
        if is_valid_ssdp_packet(data) and self.on_data:
            request, headers = decode_ssdp_packet(data, address)
            callback = self.on_data(request, headers)
            self.loop.create_task(callback)

    def error_received(self, exc) -> None:
        """Handle an error."""
        # pylint: disable=no-self-use
        _LOGGER.debug('Received error: %s', exc)

    def connection_lost(self, exc) -> None:
        """Handle connection lost."""
