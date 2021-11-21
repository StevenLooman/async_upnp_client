"""Unit tests for the IGD profile."""

import pytest

from async_upnp_client import UpnpEventHandler, UpnpFactory
from async_upnp_client.profiles.igd import IgdDevice

from ..conftest import (
    RESPONSE_MAP,
    UpnpTestNotifyServer,
    UpnpTestRequester,
    read_fixture,
)


@pytest.mark.asyncio
async def test_init_igd_profile() -> None:
    """Test if a IGD device can be initialized."""
    notify_server = UpnpTestNotifyServer()
    requester = UpnpTestRequester(RESPONSE_MAP)
    factory = UpnpFactory(requester)
    device = await factory.async_create_device("http://igd:1234/device.xml")
    event_handler = UpnpEventHandler(notify_server, requester)
    profile = IgdDevice(device, event_handler=event_handler)
    assert profile


@pytest.mark.asyncio
async def test_get_total_bytes_received() -> None:
    """Test getting total bytes received."""
    notify_server = UpnpTestNotifyServer()
    responses = dict(RESPONSE_MAP)
    responses[("POST", "http://igd:1234/WANCommonInterfaceConfig")] = (
        200,
        {},
        read_fixture("igd/action_WANCIC_GetTotalBytesReceived.xml"),
    )
    requester = UpnpTestRequester(responses)
    factory = UpnpFactory(requester)
    device = await factory.async_create_device("http://igd:1234/device.xml")
    event_handler = UpnpEventHandler(notify_server, requester)
    profile = IgdDevice(device, event_handler=event_handler)
    total_bytes_received = await profile.async_get_total_bytes_received()
    assert total_bytes_received == 1337


@pytest.mark.asyncio
async def test_get_total_packets_received_empty_response() -> None:
    """Test getting total packets received with empty response, for broken (Draytek) device."""
    notify_server = UpnpTestNotifyServer()
    responses = dict(RESPONSE_MAP)
    responses[("POST", "http://igd:1234/WANCommonInterfaceConfig")] = (
        200,
        {},
        read_fixture("igd/action_WANCIC_GetTotalPacketsReceived.xml"),
    )
    requester = UpnpTestRequester(responses)
    factory = UpnpFactory(requester)
    device = await factory.async_create_device("http://igd:1234/device.xml")
    event_handler = UpnpEventHandler(notify_server, requester)
    profile = IgdDevice(device, event_handler=event_handler)
    total_bytes_received = await profile.async_get_total_packets_received()
    assert total_bytes_received is None


@pytest.mark.asyncio
async def test_get_status_info_invalid_uptime() -> None:
    """Test getting status info with an invalid uptime response."""
    notify_server = UpnpTestNotifyServer()
    responses = dict(RESPONSE_MAP)
    responses[("POST", "http://igd:1234/WANIPConnection")] = (
        200,
        {},
        read_fixture("igd/action_WANIPConnection_GetStatusInfoInvalidUptime.xml"),
    )
    requester = UpnpTestRequester(responses)
    factory = UpnpFactory(requester)
    device = await factory.async_create_device("http://igd:1234/device.xml")
    event_handler = UpnpEventHandler(notify_server, requester)
    profile = IgdDevice(device, event_handler=event_handler)
    status_info = await profile.async_get_status_info()
    assert status_info is None
