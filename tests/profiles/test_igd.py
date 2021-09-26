"""Unit tests for the IGD profile."""

import pytest

from async_upnp_client import UpnpEventHandler, UpnpFactory
from async_upnp_client.profiles.igd import IgdDevice

from ..upnp_test_requester import RESPONSE_MAP, UpnpTestRequester


@pytest.mark.asyncio
async def test_init_igd_profile() -> None:
    """Test if a IGD device can be initialized."""
    requester = UpnpTestRequester(RESPONSE_MAP)
    factory = UpnpFactory(requester)
    device = await factory.async_create_device("http://igd:1234/device.xml")
    event_handler = UpnpEventHandler("http://localhost:11302", requester)
    profile = IgdDevice(device, event_handler=event_handler)
    assert profile


@pytest.mark.asyncio
async def test_get_total_packets_received() -> None:
    """Test getting total packets received."""
    requester = UpnpTestRequester(RESPONSE_MAP)
    factory = UpnpFactory(requester)
    device = await factory.async_create_device("http://igd:1234/device.xml")
    event_handler = UpnpEventHandler("http://localhost:11302", requester)
    profile = IgdDevice(device, event_handler=event_handler)
    total_bytes_received = await profile.async_get_total_bytes_received()
    assert total_bytes_received == 1337
