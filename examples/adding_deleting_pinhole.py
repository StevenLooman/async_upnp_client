#!/usr/bin/env python3
"""Example of adding and deleting a port mapping."""

import asyncio
import ipaddress
import sys
from datetime import timedelta
from typing import cast

from async_upnp_client.aiohttp import AiohttpRequester
from async_upnp_client.client_factory import UpnpFactory
from async_upnp_client.profiles.igd import IgdDevice
from async_upnp_client.utils import CaseInsensitiveDict, get_local_ip

SOURCE = ("0.0.0.0", 0)


async def discover_igd_devices() -> set[CaseInsensitiveDict]:
    """Discover IGD devices."""
    # Do the search, this blocks for timeout (4 seconds, default).
    discoveries = await IgdDevice.async_search(source=SOURCE)
    if not discoveries:
        print("Could not find device")
        sys.exit(1)

    return discoveries


async def build_igd_device(discovery: CaseInsensitiveDict) -> IgdDevice:
    """Find and construct device."""
    location = discovery["location"]
    requester = AiohttpRequester()
    factory = UpnpFactory(requester, non_strict=True)
    device = await factory.async_create_device(description_url=location)
    return IgdDevice(device, None)


async def async_add_pinhole(igd_device: IgdDevice) -> int:
    """Add Pinhole."""
    remote_host: ipaddress.IPv6Address = ipaddress.ip_address("::1")
    internal_client: ipaddress.IPv6Address = ipaddress.ip_address("fe80::1")
    protocol = 6  # TCP=6, UDP=17
    pinhole_id = await igd_device.async_add_pinhole(
        remote_host=remote_host,
        remote_port=43210,
        internal_client=internal_client,
        internal_port=54321,
        protocol=protocol,
        lease_time=timedelta(seconds=7200),
    )
    return pinhole_id


async def async_del_pinhole(igd_device: IgdDevice, pinhole_id: int) -> None:
    """Delete port mapping."""
    await igd_device.async_delete_pinhole(
        pinhole_id=pinhole_id,
    )


async def async_main() -> None:
    """Async main."""
    discoveries = await discover_igd_devices()
    print(f"Discoveries: {discoveries}")
    discovery = list(discoveries)[0]
    print(f"Using device at location: {discovery['location']}")
    igd_device = await build_igd_device(discovery)

    print("Creating pinhole")
    pinhole_id = await async_add_pinhole(igd_device)
    print("Pinhole ID:", pinhole_id)

    await asyncio.sleep(5)

    print("Deleting pinhole")
    await async_del_pinhole(igd_device, pinhole_id)


def main() -> None:
    """Main."""
    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
