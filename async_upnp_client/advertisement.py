# -*- coding: utf-8 -*-
"""UPnP discovery via Simple Service Discovery Protocol (SSDP)."""

import asyncio
from asyncio.events import AbstractEventLoop
from ipaddress import IPv4Address
import logging
import socket
from typing import Awaitable, Callable, Mapping, MutableMapping, Optional  # noqa: F401

from async_upnp_client.ssdp import SSDP_ALIVE
from async_upnp_client.ssdp import SSDP_BYEBYE
from async_upnp_client.ssdp import SSDP_TARGET
from async_upnp_client.ssdp import SSDP_UPDATE
from async_upnp_client.ssdp import SsdpProtocol


_LOGGER = logging.getLogger(__name__)


class UpnpAdvertisementListener:
    """UPnP Advertisement listener."""

    def __init__(self,
                 on_alive: Optional[Callable[[Mapping[str, str]], Awaitable]] = None,
                 on_byebye: Optional[Callable[[Mapping[str, str]], Awaitable]] = None,
                 on_update: Optional[Callable[[Mapping[str, str]], Awaitable]] = None,
                 source_ip: Optional[IPv4Address] = None,
                 loop: Optional[AbstractEventLoop] = None) -> None:
        """Initializer."""
        # pylint: disable=too-many-arguments
        self.on_alive = on_alive
        self.on_byebye = on_byebye
        self.on_update = on_update
        self._loop = loop or asyncio.get_event_loop()  # type: AbstractEventLoop
        self._transport = None  # type: Optional[asyncio.DatagramTransport]

        self._connect = self._create_protocol(source_ip)

    def _create_protocol(self, source_ip: Optional[IPv4Address]) -> Awaitable:
        """Create a socket to listen on."""
        source_ip = source_ip or IPv4Address('0.0.0.0')

        # create socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setsockopt(socket.SOL_IP, socket.IP_MULTICAST_IF, source_ip.packed)

        # multicast
        sock.setsockopt(socket.IPPROTO_IP,
                        socket.IP_ADD_MEMBERSHIP,
                        IPv4Address(SSDP_TARGET[0]).packed + source_ip.packed)
        sock.bind(SSDP_TARGET)

        # create protocol and send discovery packet
        connect = self._loop.create_datagram_endpoint(
            lambda: SsdpProtocol(self._loop, on_data=self._on_data),
            sock=sock,
        )
        return connect

    async def _on_data(self, request_line: str, headers: MutableMapping[str, str]) -> None:
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

    async def async_start(self) -> None:
        """Start listening for notifications."""
        self._transport, _ = await self._connect

    async def async_stop(self) -> None:
        """Stop listening for notifications."""
        if self._transport:
            self._transport.close()
