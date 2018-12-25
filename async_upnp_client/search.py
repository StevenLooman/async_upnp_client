# -*- coding: utf-8 -*-
"""UPnP discovery via Simple Service Discovery Protocol (SSDP)."""
import asyncio
import logging
import socket

from ipaddress import IPv4Address
from typing import Optional

from async_upnp_client.ssdp import build_ssdp_search_packet
from async_upnp_client.ssdp import SsdpProtocol
from async_upnp_client.ssdp import SSDP_MX
from async_upnp_client.ssdp import SSDP_ST_ALL
from async_upnp_client.ssdp import SSDP_TARGET


_LOGGER = logging.getLogger(__name__)


async def async_search(timeout: int = SSDP_MX,
                       service_type: str = SSDP_ST_ALL,
                       source_ip: Optional[IPv4Address] = None,
                       async_callback=None,
                       loop=None) -> None:
    """Discover devices via SSDP."""
    loop = loop or asyncio.get_event_loop()

    # create socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    if source_ip:
        sock.bind((source_ip, 0))

    async def on_connect(transport):
        """Handle connection made."""
        packet = build_ssdp_search_packet(SSDP_TARGET, timeout, service_type)
        transport.sendto(packet, SSDP_TARGET)

    async def on_data(request_line, headers):
        """Handle data."""
        # pylint: disable=unused-argument
        headers['_source'] = 'search'
        await async_callback(headers)

    # create protocol and send discovery packet
    connect = loop.create_datagram_endpoint(
        lambda: SsdpProtocol(loop, on_connect=on_connect, on_data=on_data),
        sock=sock,
    )
    transport, _ = await connect

    # wait for devices to respond
    await asyncio.sleep(timeout)

    # fin
    transport.close()
