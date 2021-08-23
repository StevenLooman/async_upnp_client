# -*- coding: utf-8 -*-
"""UPnP discovery via Simple Service Discovery Protocol (SSDP)."""

import asyncio
import logging
from asyncio.events import AbstractEventLoop
from asyncio.transports import BaseTransport
from ipaddress import IPv4Address
from typing import Any, Awaitable, Callable, MutableMapping, Optional

from async_upnp_client.const import NotificationSubType
from async_upnp_client.ssdp import (
    SSDP_DISCOVER,
    SSDP_IP_V4,
    IPvXAddress,
    SsdpProtocol,
    get_source_ip_from_target_ip,
    get_ssdp_socket,
    udn_from_headers,
)

_LOGGER = logging.getLogger(__name__)
_LOGGER_TRAFFIC_SSDP = logging.getLogger("async_upnp_client.traffic.ssdp")


class SsdpAdvertisementListener:
    """SSDP Advertisement listener."""

    def __init__(
        self,
        on_alive: Optional[Callable[[MutableMapping[str, str]], Awaitable]] = None,
        on_byebye: Optional[Callable[[MutableMapping[str, str]], Awaitable]] = None,
        on_update: Optional[Callable[[MutableMapping[str, str]], Awaitable]] = None,
        source_ip: Optional[IPvXAddress] = None,
        target_ip: Optional[IPvXAddress] = None,
        loop: Optional[AbstractEventLoop] = None,
    ) -> None:
        """Initialize."""
        # pylint: disable=too-many-arguments
        self.on_alive = on_alive
        self.on_byebye = on_byebye
        self.on_update = on_update
        self.target_ip = target_ip or IPv4Address(SSDP_IP_V4)
        self.source_ip = source_ip or get_source_ip_from_target_ip(self.target_ip)
        self._loop: AbstractEventLoop = loop or asyncio.get_event_loop()
        self._transport: Optional[BaseTransport] = None

    async def _async_on_data(
        self, request_line: str, headers: MutableMapping[str, Any]
    ) -> None:
        """Handle data."""
        _LOGGER_TRAFFIC_SSDP.debug(
            "SsdpAdvertisementListener._async_on_data: %s, %s", request_line, headers
        )
        if headers.get("MAN") == SSDP_DISCOVER:
            # Ignore discover packets.
            return
        if "NTS" not in headers:
            _LOGGER.debug("Got unknown packet: %s, %s", request_line, headers)
            return

        _LOGGER.debug(
            "Received advertisement, request line: %s, headers: %s",
            request_line,
            headers,
        )

        udn = udn_from_headers(headers)
        if udn:
            headers["_udn"] = udn
        headers["_source"] = "advertisement"
        notification_sub_type = headers["NTS"]
        if notification_sub_type == NotificationSubType.SSDP_ALIVE and self.on_alive:
            await self.on_alive(headers)
        elif (
            notification_sub_type == NotificationSubType.SSDP_BYEBYE and self.on_byebye
        ):
            await self.on_byebye(headers)
        elif (
            notification_sub_type == NotificationSubType.SSDP_UPDATE and self.on_update
        ):
            await self.on_update(headers)

    async def async_start(self) -> None:
        """Start listening for advertisements."""
        _LOGGER.debug("Start listening for advertisements")

        # Construct a socket for use with this pairs of endpoints.
        sock, _, target = get_ssdp_socket(self.source_ip, self.target_ip)
        sock.bind(target)

        # Create protocol and send discovery packet.
        self._transport, _ = await self._loop.create_datagram_endpoint(
            lambda: SsdpProtocol(self._loop, on_data=self._async_on_data),
            sock=sock,
        )

    async def async_stop(self) -> None:
        """Stop listening for advertisements."""
        _LOGGER.debug("Stop listening for advertisements")
        if self._transport:
            self._transport.close()
