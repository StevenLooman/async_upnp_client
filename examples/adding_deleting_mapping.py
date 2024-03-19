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


async def async_add_port_mapping(igd_device: IgdDevice) -> None:
    """Add port mapping."""
    external_ip_address = await igd_device.async_get_external_ip_address()
    if not external_ip_address:
        print("Could not get external IP address")
        sys.exit(1)

    remote_host = ipaddress.ip_address(external_ip_address)
    remote_host_ipv4 = cast(ipaddress.IPv4Address, remote_host)
    local_ip = ipaddress.ip_address(get_local_ip())
    local_ip_ipv4 = cast(ipaddress.IPv4Address, local_ip)
    # Change `enabled` to False to disable port mapping.
    # NB: This does not delete the port mapping.
    enabled = True
    mapping_name = "Bombsquad"
    await igd_device.async_add_port_mapping(
        remote_host=remote_host_ipv4,
        external_port=43210,
        internal_client=local_ip_ipv4,
        internal_port=43210,
        protocol="UDP",
        enabled=enabled,
        description=mapping_name,
        lease_duration=timedelta(seconds=7200),
    )  # Time in secs


async def async_del_port_mapping(igd_device: IgdDevice) -> None:
    """Delete port mapping."""
    external_ip_address = await igd_device.async_get_external_ip_address()
    if not external_ip_address:
        print("Could not get external IP address")
        sys.exit(1)

    remote_host = ipaddress.ip_address(external_ip_address)
    remote_host_ipv4 = cast(ipaddress.IPv4Address, remote_host)
    await igd_device.async_delete_port_mapping(
        remote_host=remote_host_ipv4,
        external_port=43210,
        protocol="UDP",
    )


async def async_main() -> None:
    """Async main."""
    discoveries = await discover_igd_devices()
    print(f"Discoveries: {discoveries}")
    discovery = list(discoveries)[0]
    print(f"Using device at location: {discovery['location']}")
    igd_device = await build_igd_device(discovery)

    print("Creating port mapping")
    await async_add_port_mapping(igd_device)

    await asyncio.sleep(60)

    print("Deleting port mapping")
    await async_del_port_mapping(igd_device)


def main() -> None:
    """Main."""
    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
