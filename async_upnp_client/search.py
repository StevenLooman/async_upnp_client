# -*- coding: utf-8 -*-
"""UPnP discovery via Simple Service Discovery Protocol (SSDP)."""
import asyncio
from asyncio import DatagramTransport
from asyncio.events import AbstractEventLoop
import logging
import socket
from ipaddress import IPv4Address
from typing import Awaitable, Callable, Mapping, MutableMapping, Optional

from async_upnp_client.ssdp import SSDP_MX
from async_upnp_client.ssdp import SSDP_ST_ALL
from async_upnp_client.ssdp import SSDP_TARGET
from async_upnp_client.ssdp import SSDP_PORT
from async_upnp_client.ssdp import SsdpProtocol
from async_upnp_client.ssdp import build_ssdp_search_packet

_LOGGER = logging.getLogger(__name__)


async def async_search(async_callback: Callable[[Mapping[str, str]], Awaitable],
                       timeout: int = SSDP_MX,
                       service_type: str = SSDP_ST_ALL,
                       source_ip: Optional[IPv4Address] = None,
                       loop: Optional[AbstractEventLoop] = None,
                       target_ip: Optional[IPv4Address] = None) -> None:
    """Discover devices via SSDP."""
    source_ip = source_ip or IPv4Address('0.0.0.0')
    loop_: AbstractEventLoop = loop or asyncio.get_event_loop()

    if target_ip:
        target = (str(target_ip), SSDP_PORT)
        # We use the standard target in the data of the announce since
        # many implementations will ignore the request otherwise
        target_data = SSDP_TARGET
    else:
        target = SSDP_TARGET
        target_data = SSDP_TARGET

    # Create socket.
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((source_ip.compressed, 0))

    async def on_connect(transport: DatagramTransport) -> None:
        """Handle connection made."""
        packet = build_ssdp_search_packet(target_data, timeout, service_type)
        transport.sendto(packet, target)

    async def on_data(_: str, headers: MutableMapping[str, str]) -> None:
        """Handle data."""
        headers['_source'] = 'search'
        if target_ip:
            if headers['_address'].partition(":")[0] != f"{str(target_ip)}":
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
