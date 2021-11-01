# -*- coding: utf-8 -*-
"""UPnP discovery via Simple Service Discovery Protocol (SSDP)."""
import asyncio
import logging
from asyncio import DatagramTransport
from asyncio.events import AbstractEventLoop
from typing import Awaitable, Callable, Optional, Union, cast

from async_upnp_client.const import SsdpSource
from async_upnp_client.ssdp import (
    SSDP_DISCOVER,
    SSDP_MX,
    SSDP_ST_ALL,
    AddressTupleVXType,
    IPvXAddress,
    SsdpHeaders,
    SsdpProtocol,
    build_ssdp_search_packet,
    get_host_string,
    get_source_address_tuple,
    get_ssdp_socket,
    get_target_address_tuple,
    ip_address_from_address_tuple,
)

_LOGGER = logging.getLogger(__name__)


class SsdpSearchListener:  # pylint: disable=too-many-arguments,too-many-instance-attributes
    """SSDP Search (response) listener."""

    def __init__(
        self,
        async_callback: Callable[[SsdpHeaders], Awaitable],
        loop: Optional[AbstractEventLoop] = None,
        source: Union[AddressTupleVXType, IPvXAddress, None] = None,
        target: Union[AddressTupleVXType, IPvXAddress, None] = None,
        timeout: int = SSDP_MX,
        service_type: str = SSDP_ST_ALL,
        async_connect_callback: Optional[Callable[[], Awaitable]] = None,
    ) -> None:
        """Init the ssdp listener class."""
        self.async_callback = async_callback
        self.async_connect_callback = async_connect_callback
        self.service_type = service_type
        self.target = get_target_address_tuple(target)
        self.source = get_source_address_tuple(self.target, source)
        self.timeout = timeout
        self.loop = loop
        self._target_host: Optional[str] = None
        self._transport: Optional[DatagramTransport] = None

    def async_search(
        self, override_target: Optional[AddressTupleVXType] = None
    ) -> None:
        """Start an SSDP search."""
        assert self._target_host is not None, "Call async_start() first"
        packet = build_ssdp_search_packet(self.target, self.timeout, self.service_type)

        assert self._transport is not None
        protocol = cast(SsdpProtocol, self._transport.get_protocol())
        target = override_target or self.target
        protocol.send_ssdp_packet(packet, target)

    async def _async_on_data(self, request_line: str, headers: SsdpHeaders) -> None:
        """Handle data."""
        if headers.get("MAN") == SSDP_DISCOVER:
            # Ignore discover packets.
            return
        if "NTS" in headers:
            _LOGGER.debug(
                "Got non-search response packet: %s, %s", request_line, headers
            )
            return

        _LOGGER.debug("Received response, USN: %s", headers.get("USN", "<no USN>"))
        headers["_source"] = SsdpSource.SEARCH
        if self._target_host and self._target_host != headers["_host"]:
            return
        await self.async_callback(headers)

    async def _async_on_connect(self, transport: DatagramTransport) -> None:
        self._transport = transport
        if self.async_connect_callback:
            await self.async_connect_callback()

    async def async_start(self) -> None:
        """Start the listener."""
        # We use the standard target in the data of the announce since
        # many implementations will ignore the request otherwise
        sock, sock_source, _ = get_ssdp_socket(self.source, self.target)

        target_ip = ip_address_from_address_tuple(self.target)
        if not target_ip.is_multicast:
            self._target_host = get_host_string(self.target)
        else:
            self._target_host = ""

        sock.bind(sock_source)

        loop = self.loop or asyncio.get_event_loop()
        await loop.create_datagram_endpoint(
            lambda: SsdpProtocol(
                loop, on_connect=self._async_on_connect, on_data=self._async_on_data
            ),
            sock=sock,
        )

    def async_stop(self) -> None:
        """Stop the listener."""
        if self._transport:
            self._transport.close()


async def async_search(
    async_callback: Callable[[SsdpHeaders], Awaitable],
    timeout: int = SSDP_MX,
    service_type: str = SSDP_ST_ALL,
    source: Union[IPvXAddress, AddressTupleVXType, None] = None,
    target: Union[IPvXAddress, AddressTupleVXType, None] = None,
    loop: Optional[AbstractEventLoop] = None,
) -> None:
    """Discover devices via SSDP."""
    # pylint: disable=too-many-arguments
    loop_: AbstractEventLoop = loop or asyncio.get_event_loop()
    listener: Optional[SsdpSearchListener] = None

    async def _async_connected() -> None:
        nonlocal listener
        assert listener is not None
        listener.async_search()

    listener = SsdpSearchListener(
        async_callback=async_callback,
        loop=loop_,
        source=source,
        target=target,
        timeout=timeout,
        service_type=service_type,
        async_connect_callback=_async_connected,
    )

    await listener.async_start()

    # Wait for devices to respond.
    await asyncio.sleep(timeout)

    listener.async_stop()
