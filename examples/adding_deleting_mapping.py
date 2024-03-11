#!/usr/bin/env python3
from async_upnp_client.aiohttp import AiohttpRequester
from async_upnp_client.event_handler import UpnpEventHandler
from async_upnp_client.client import UpnpDevice
from async_upnp_client.client_factory import UpnpFactory
from async_upnp_client.profiles.igd import IgdDevice
from async_upnp_client.search import async_search
from typing import Optional
from async_upnp_client.ssdp import SSDP_ST_ROOTDEVICE
from async_upnp_client.utils import get_local_ip
from datetime import timedelta
import asyncio
import sys
import ipaddress


async def build_device(search_target: str) -> UpnpDevice:
    """Find and construct device."""
    location: Optional[str] = None
    async def callback(headers) -> None:
        """Search callback."""
        nonlocal location
        location = headers['location']

    # Do the search, this blocks for timeout (4 seconds, default).
    await async_search(callback, search_target=search_target)

    if location:
        requester = AiohttpRequester()
        factory = UpnpFactory(requester, non_strict=True)
        device = await factory.async_create_device(description_url=location)
        return device

async def async_add() -> None:
    """Add port mapping."""
    device = await build_device(search_target=SSDP_ST_ROOTDEVICE)
    if not device:
        print("Could not find device")
        sys.exit(1)
    igd_device = IgdDevice(device, UpnpEventHandler)
    remote_host = ipaddress.ip_address(await igd_device.async_get_external_ip_address())
    local_ip = ipaddress.ip_address(get_local_ip())
    await igd_device.async_add_port_mapping(
        remote_host =remote_host,
        external_port=43210,
        protocol="UDP",
        internal_port=43210,
        internal_client=local_ip,
        enabled=True, #  Change to False to disable port mapping(NB - This does not delete the port mapping)
        description="Bombsquad", # Name of the port mapping
        lease_duration=timedelta(seconds=7200),) # Time in secs

async def async_del() -> None:
    """Delete port mapping."""
    
    device = await build_device(search_target=SSDP_ST_ROOTDEVICE)
    if not device:
        print("Could not find device")
        sys.exit(1)
    igd_device = IgdDevice(device, UpnpEventHandler)
    remote_host = ipaddress.ip_address(await igd_device.async_get_external_ip_address())
    
    await igd_device.async_delete_port_mapping(
        remote_host =remote_host,
        external_port=43210,
        protocol="UDP",)
    

def main() -> None:
    try:
        asyncio.run(async_add()) # Change to async_del() to delete port mapping
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
