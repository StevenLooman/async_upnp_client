# -*- coding: utf-8 -*-
"""UPnP discovery via Simple Service Discovery Protocol (SSDP)."""

import asyncio
import logging
from asyncio.events import AbstractEventLoop
from ipaddress import IPv4Address
from typing import Awaitable, Callable, Mapping, MutableMapping, Optional

from async_upnp_client.ssdp import (
    IPvXAddress,
    SSDP_ALIVE,
    SSDP_BYEBYE,
    SSDP_IP_V4,
    SSDP_UPDATE,
    SsdpProtocol,
    get_source_ip_from_target_ip,
    get_ssdp_socket,
)

_LOGGER = logging.getLogger(__name__)


class UpnpAdvertisementListener:
    """UPnP Advertisement listener."""

    def __init__(
        self,
        on_alive: Optional[Callable[[Mapping[str, str]], Awaitable]] = None,
        on_byebye: Optional[Callable[[Mapping[str, str]], Awaitable]] = None,
        on_update: Optional[Callable[[Mapping[str, str]], Awaitable]] = None,
        source_ip: Optional[IPvXAddress] = None,
        target_ip: Optional[IPvXAddress] = None,
        loop: Optional[AbstractEventLoop] = None,
    ) -> None:
        """Initialize."""
        # pylint: disable=too-many-arguments
        self.on_alive = on_alive
        self.on_byebye = on_byebye
        self.on_update = on_update
        self._loop: AbstractEventLoop = loop or asyncio.get_event_loop()
        self._transport: Optional[asyncio.DatagramTransport] = None

        self._connect = self._create_protocol(source_ip, target_ip)

    def _create_protocol(
        self, source_ip: Optional[IPvXAddress], target_ip: Optional[IPvXAddress]
    ) -> Awaitable:
        """Create a socket to listen on."""
        if target_ip is None:
            target_ip = IPv4Address(SSDP_IP_V4)
        if source_ip is None:
            source_ip = get_source_ip_from_target_ip(target_ip)

        # construct a socket for use with this pairs of endpoints
        sock, _, target = get_ssdp_socket(source_ip, target_ip)
        sock.bind(target)

        # create protocol and send discovery packet
        connect = self._loop.create_datagram_endpoint(
            lambda: SsdpProtocol(self._loop, on_data=self._on_data),
            sock=sock,
        )
        return connect

    async def _on_data(
        self, request_line: str, headers: MutableMapping[str, str]
    ) -> None:
        """Handle data."""
        _LOGGER.debug(
            "UpnpAdvertisementListener._on_data: %s, %s", request_line, headers
        )
        if "NTS" not in headers:
            _LOGGER.debug("Got unknown packet: %s, %s", request_line, headers)
            return

        headers["_source"] = "advertisement"
        data_type = headers["NTS"]
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
