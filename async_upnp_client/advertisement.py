# -*- coding: utf-8 -*-
"""UPnP discovery via Simple Service Discovery Protocol (SSDP)."""

import asyncio
import logging
from asyncio.events import AbstractEventLoop
from asyncio.transports import BaseTransport, DatagramTransport
from typing import Awaitable, Callable, Optional, Union

from async_upnp_client.const import AddressTupleVXType, NotificationSubType, SsdpSource
from async_upnp_client.net import get_source_address_tuple
from async_upnp_client.ssdp import (
    SSDP_DISCOVER,
    IPvXAddress,
    SsdpHeaders,
    SsdpProtocol,
    get_ssdp_socket,
    get_target_address_tuple,
)

_LOGGER = logging.getLogger(__name__)


class SsdpAdvertisementListener:
    """SSDP Advertisement listener."""

    def __init__(
        self,
        on_alive: Optional[
            Callable[[SsdpHeaders, AddressTupleVXType], Awaitable]
        ] = None,
        on_byebye: Optional[
            Callable[[SsdpHeaders, AddressTupleVXType], Awaitable]
        ] = None,
        on_update: Optional[
            Callable[[SsdpHeaders, AddressTupleVXType], Awaitable]
        ] = None,
        source: Union[AddressTupleVXType, IPvXAddress, None] = None,
        target: Union[AddressTupleVXType, IPvXAddress, None] = None,
        loop: Optional[AbstractEventLoop] = None,
    ) -> None:
        """Initialize."""
        # pylint: disable=too-many-arguments
        self.on_alive = on_alive
        self.on_byebye = on_byebye
        self.on_update = on_update
        self.target = get_target_address_tuple(target, source=source)
        self.source = get_source_address_tuple(self.target, source)
        self._loop: AbstractEventLoop = loop or asyncio.get_event_loop()
        self._transport: Optional[BaseTransport] = None

    async def _async_on_data(
        self, request_line: str, headers: SsdpHeaders, addr: AddressTupleVXType
    ) -> None:
        """Handle data."""
        if headers.get("MAN") == SSDP_DISCOVER:
            # Ignore discover packets.
            return
        if "NTS" not in headers:
            _LOGGER.debug(
                "Ignoring non-advertisement packet: %s, %s", request_line, headers
            )
            return

        _LOGGER.debug("Received advertisement, USN: %s", headers.get("USN", "<no USN>"))

        headers["_source"] = SsdpSource.ADVERTISEMENT
        notification_sub_type = headers["NTS"]
        if notification_sub_type == NotificationSubType.SSDP_ALIVE and self.on_alive:
            await self.on_alive(headers, addr)
        elif (
            notification_sub_type == NotificationSubType.SSDP_BYEBYE and self.on_byebye
        ):
            await self.on_byebye(headers, addr)
        elif (
            notification_sub_type == NotificationSubType.SSDP_UPDATE and self.on_update
        ):
            await self.on_update(headers, addr)

    async def _async_on_connect(self, transport: DatagramTransport) -> None:
        self._transport = transport

    async def async_start(self) -> None:
        """Start listening for advertisements."""
        _LOGGER.debug("Start listening for advertisements")

        # Construct a socket for use with this pairs of endpoints.
        sock, _, sock_target = get_ssdp_socket(self.source, self.target)
        _LOGGER.debug("Binding to address: %s", sock_target)
        sock.bind(sock_target)

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
