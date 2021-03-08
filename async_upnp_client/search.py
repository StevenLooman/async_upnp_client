# -*- coding: utf-8 -*-
"""UPnP discovery via Simple Service Discovery Protocol (SSDP)."""
import asyncio
import logging
from asyncio import DatagramTransport
from asyncio.events import AbstractEventLoop
from ipaddress import IPv4Address, IPv6Address
from typing import Awaitable, Callable, Mapping, MutableMapping, Optional

from async_upnp_client.ssdp import (
    IPvXAddress,
    SSDP_IP_V4,
    SSDP_MX,
    SSDP_ST_ALL,
    SSDP_TARGET_V4,
    SSDP_TARGET_V6,
    SsdpProtocol,
    build_ssdp_search_packet,
    get_source_ip_from_target_ip,
    get_ssdp_socket,
)

_LOGGER = logging.getLogger(__name__)


async def async_search(
    async_callback: Callable[[Mapping[str, str]], Awaitable],
    timeout: int = SSDP_MX,
    service_type: str = SSDP_ST_ALL,
    source_ip: Optional[IPvXAddress] = None,
    loop: Optional[AbstractEventLoop] = None,
    target_ip: Optional[IPvXAddress] = None,
) -> None:
    """Discover devices via SSDP."""
    # pylint: disable=too-many-arguments,too-many-locals
    loop_: AbstractEventLoop = loop or asyncio.get_event_loop()

    if target_ip is None:
        target_ip = IPv4Address(SSDP_IP_V4)
    if source_ip is None:
        source_ip = get_source_ip_from_target_ip(target_ip)

    sock, source, target = get_ssdp_socket(source_ip, target_ip)

    # We use the standard target in the data of the announce since
    # many implementations will ignore the request otherwise
    if isinstance(target_ip, IPv6Address):
        target_data = SSDP_TARGET_V6
    else:
        target_data = SSDP_TARGET_V4
    sock.bind(source)

    async def on_connect(transport: DatagramTransport) -> None:
        """Handle connection made."""
        packet = build_ssdp_search_packet(target_data, timeout, service_type)
        transport.sendto(packet, target)

    async def on_data(_: str, headers: MutableMapping[str, str]) -> None:
        """Handle data."""
        headers["_source"] = "search"
        is_multicast = getattr(target_ip, "is_multicast", True)
        if not is_multicast:
            if headers["_address"].partition(":")[0] != f"{str(target_ip)}":
                return
        await async_callback(headers)

    # Create protocol and send discovery packet.
    connect = loop_.create_datagram_endpoint(
        lambda: SsdpProtocol(loop_, on_connect=on_connect, on_data=on_data),
        sock=sock,
    )
    transport, _ = await connect

    # Wait for devices to respond.
    await asyncio.sleep(timeout)

    # Fin.
    transport.close()
