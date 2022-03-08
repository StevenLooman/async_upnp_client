# -*- coding: utf-8 -*-
"""async_upnp_client.advertisement module."""

import asyncio
import logging
import sys
from asyncio.events import AbstractEventLoop
from asyncio.transports import BaseTransport, DatagramTransport
from typing import Awaitable, Callable, Optional

from async_upnp_client.const import AddressTupleVXType, NotificationSubType, SsdpSource
from async_upnp_client.ssdp import (
    SSDP_DISCOVER,
    SsdpHeaders,
    SsdpProtocol,
    determine_source_target,
    get_ssdp_socket,
)

_LOGGER = logging.getLogger(__name__)


class SsdpAdvertisementListener:
    """SSDP Advertisement listener."""

    def __init__(
        self,
        on_alive: Optional[Callable[[SsdpHeaders], Awaitable]] = None,
        on_byebye: Optional[Callable[[SsdpHeaders], Awaitable]] = None,
        on_update: Optional[Callable[[SsdpHeaders], Awaitable]] = None,
        source: Optional[AddressTupleVXType] = None,
        target: Optional[AddressTupleVXType] = None,
        loop: Optional[AbstractEventLoop] = None,
    ) -> None:
        """Initialize."""
        # pylint: disable=too-many-arguments
        self.on_alive = on_alive
        self.on_byebye = on_byebye
        self.on_update = on_update
        self.source, self.target = determine_source_target(source, target)
        self._loop: AbstractEventLoop = loop or asyncio.get_event_loop()
        self._transport: Optional[BaseTransport] = None

    async def _async_on_data(self, request_line: str, headers: SsdpHeaders) -> None:
        """Handle data."""
        if headers.get("MAN") == SSDP_DISCOVER:
            # Ignore discover packets.
            return
        if "NTS" not in headers:
            _LOGGER.debug("Got non-advertisement packet: %s, %s", request_line, headers)
            return

        _LOGGER.debug(
            "Received advertisement, USN: %s, location: %s",
            headers.get("USN", "<no USN>"),
            headers.get("location", ""),
        )

        headers["_source"] = SsdpSource.ADVERTISEMENT
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

    async def _async_on_connect(self, transport: DatagramTransport) -> None:
        _LOGGER.debug("On connect, transport: %s", transport)
        self._transport = transport

    async def async_start(self) -> None:
        """Start listening for advertisements."""
        _LOGGER.debug("Start listening for advertisements")

        # Construct a socket for use with this pairs of endpoints.
        sock, source, target = get_ssdp_socket(self.source, self.target)
        address = source if sys.platform == "win32" else target
        _LOGGER.debug("Binding to address: %s", address)
        sock.bind(address)

        # Create protocol and send discovery packet.
        await self._loop.create_datagram_endpoint(
            lambda: SsdpProtocol(
                self._loop,
                on_connect=self._async_on_connect,
                on_data=self._async_on_data,
            ),
            sock=sock,
        )

    async def async_stop(self) -> None:
        """Stop listening for advertisements."""
        _LOGGER.debug("Stop listening for advertisements")
        if self._transport:
            self._transport.close()
