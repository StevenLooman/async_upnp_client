# -*- coding: utf-8 -*-
"""UPnP discovery via Simple Service Discovery Protocol (SSDP)."""

import asyncio
import logging
import socket
import struct

from async_upnp_client.ssdp import SsdpProtocol
from async_upnp_client.ssdp import SSDP_ALIVE
from async_upnp_client.ssdp import SSDP_BYEBYE
from async_upnp_client.ssdp import SSDP_TARGET
from async_upnp_client.ssdp import SSDP_UPDATE


_LOGGER = logging.getLogger(__name__)


class UpnpAdvertisementListener:
    """UPnP Advertisement listener."""

    def __init__(self, on_alive=None, on_byebye=None, on_update=None, loop=None):
        """Initializer."""
        self.on_alive = on_alive
        self.on_byebye = on_byebye
        self.on_update = on_update
        self._loop = loop or asyncio.get_event_loop()
        self._transport = None

        self._connect = self._create_protocol()

    def _create_protocol(self):
        """Create a socket to listen on."""
        # create socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        # multicast
        mreq = struct.pack("4sl", socket.inet_aton(SSDP_TARGET[0]), socket.INADDR_ANY)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
        sock.bind(SSDP_TARGET)

        # create protocol and send discovery packet
        connect = self._loop.create_datagram_endpoint(
            lambda: SsdpProtocol(self._loop, on_data=self._on_data),
            sock=sock,
        )
        return connect

    async def _on_data(self, request_line, headers):
        """Handle data."""
        _LOGGER.debug('UpnpAdvertisementListener._on_data: %s, %s', request_line, headers)
        if 'NTS' not in headers:
            _LOGGER.debug('Got unknown packet: %s, %s', request_line, headers)
            return

        headers['_source'] = 'advertisement'
        data_type = headers['NTS']
        if data_type == SSDP_ALIVE and self.on_alive:
            await self.on_alive(headers)
        elif data_type == SSDP_BYEBYE and self.on_byebye:
            await self.on_byebye(headers)
        elif data_type == SSDP_UPDATE and self.on_update:
            await self.on_update(headers)

    async def async_start(self):
        """Start listening for notifications."""
        self._transport, _ = await self._connect

    async def async_stop(self):
        """Stop listening for notifications."""
        self._transport.close()
