# -*- coding: utf-8 -*-
"""UPnP discovery via Simple Service Discovery Protocol (SSDP)."""
import asyncio
import logging
from asyncio import DatagramTransport
from asyncio.events import AbstractEventLoop
from ipaddress import ip_address
from typing import Awaitable, Callable, Mapping, MutableMapping, Optional

from async_upnp_client.ssdp import (
    SSDP_IP_V4,
    SSDP_IP_V6,
    SSDP_MX,
    SSDP_PORT,
    SSDP_ST_ALL,
    AddressTupleVXType,
    IPvXAddress,
    SsdpProtocol,
    build_ssdp_search_packet,
    get_host_string,
    get_source_ip_from_target_ip,
    get_ssdp_socket,
)

_LOGGER = logging.getLogger(__name__)
_LOGGER_TRAFFIC_SSDP = logging.getLogger("async_upnp_client.traffic.ssdp")


class SSDPListener:  # pylint: disable=too-many-arguments,too-many-instance-attributes
    """Class to listen for SSDP."""

    def __init__(
        self,
        async_callback: Callable[[Mapping[str, str]], Awaitable],
        loop: Optional[AbstractEventLoop] = None,
        source_ip: Optional[IPvXAddress] = None,
        target: Optional[AddressTupleVXType] = None,
        timeout: int = SSDP_MX,
        service_type: str = SSDP_ST_ALL,
        async_connect_callback: Optional[Callable[[], Awaitable]] = None,
    ) -> None:
        """Init the ssdp listener class."""
        self.async_callback = async_callback
        self.async_connect_callback = async_connect_callback
        self.service_type = service_type
        self.source_ip = source_ip
        self.timeout = timeout
        self.loop = loop
        self._target: Optional[AddressTupleVXType] = target
        self._target_host: Optional[str] = None
        self._transport: Optional[DatagramTransport] = None

    def async_search(
        self, override_target: Optional[AddressTupleVXType] = None
    ) -> None:
        """Start an SSDP search."""
        assert self._target_host is not None, "Call async_start() first"
        assert self._target is not None, "Call async_start() first"
        packet = build_ssdp_search_packet(self._target, self.timeout, self.service_type)
        _LOGGER.debug("Sending M-SEARCH packet, transport: %s", self._transport)
        _LOGGER_TRAFFIC_SSDP.debug("Sending M-SEARCH packet: %s", packet)
        assert self._transport is not None
        target = override_target or self._target
        self._transport.sendto(packet, target)

    async def _async_on_data(
        self, request_line: str, headers: MutableMapping[str, str]
    ) -> None:
        _LOGGER.debug(
            "Received response, request line: %s, headers: %s", request_line, headers
        )
        headers["_source"] = "search"
        if self._target_host and self._target_host != headers["_host"]:
            return
        await self.async_callback(headers)

    async def _async_on_connect(self, transport: DatagramTransport) -> None:
        self._transport = transport
        if self.async_connect_callback:
            await self.async_connect_callback()

    async def async_start(self) -> None:
        """Start the listener."""
        if self._target is None:
            if self.source_ip and self.source_ip.version == 6:
                self._target = (SSDP_IP_V6, SSDP_PORT)
            else:
                self._target = (SSDP_IP_V4, SSDP_PORT)

        target_ip: IPvXAddress = ip_address(self._target[0])

        if self.source_ip is None:
            self.source_ip = get_source_ip_from_target_ip(target_ip)
        # We use the standard target in the data of the announce since
        # many implementations will ignore the request otherwise
        sock, source, _ = get_ssdp_socket(
            self.source_ip, target_ip, port=self._target[1]
        )

        if not target_ip.is_multicast:
            self._target_host = get_host_string(self._target)
        else:
            self._target_host = ""

        sock.bind(source)
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
    async_callback: Callable[[Mapping[str, str]], Awaitable],
    timeout: int = SSDP_MX,
    service_type: str = SSDP_ST_ALL,
    source_ip: Optional[IPvXAddress] = None,
    loop: Optional[AbstractEventLoop] = None,
    target: Optional[AddressTupleVXType] = None,
) -> None:
    """Discover devices via SSDP."""
    # pylint: disable=too-many-arguments
    loop_: AbstractEventLoop = loop or asyncio.get_event_loop()
    listener: Optional[SSDPListener] = None

    async def _async_connected() -> None:
        nonlocal listener
        assert listener is not None
        listener.async_search()

    listener = SSDPListener(
        async_callback,
        loop_,
        source_ip,
        target,
        timeout,
        service_type,
        async_connect_callback=_async_connected,
    )

    await listener.async_start()

    # Wait for devices to respond.
    await asyncio.sleep(timeout)

    listener.async_stop()
