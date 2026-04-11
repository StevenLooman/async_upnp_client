"""Unit tests for the IGD profile."""

from datetime import datetime, timedelta

import pytest

from async_upnp_client.client import UpnpDevice
from async_upnp_client.client_factory import UpnpFactory
from async_upnp_client.const import HttpResponse
from async_upnp_client.event_handler import UpnpEventHandler
from async_upnp_client.profiles.igd import (
    IgdDevice,
    IgdStateItem,
    TrafficCounterState,
)

from ..conftest import RESPONSE_MAP, UpnpTestNotifyServer, UpnpTestRequester, read_file


class FixedCounterIgdDevice(IgdDevice):
    """IGD device with deterministic counters for overflow tests."""

    def __init__(
        self,
        device: UpnpDevice,
        event_handler: UpnpEventHandler | None,
        initial_traffic_state: TrafficCounterState,
        current_traffic_state: TrafficCounterState,
    ) -> None:
        """Initialize test device with fixed traffic counters."""
        super().__init__(device, event_handler)
        self._last_traffic_state = initial_traffic_state
        self._current_traffic_state = current_traffic_state

    async def async_poll_traffic_data(
        self,
        items: set[IgdStateItem],
    ) -> TrafficCounterState:
        """Return a fixed traffic state for tests."""
        return self._current_traffic_state


@pytest.mark.asyncio
async def test_init_igd_profile() -> None:
    """Test if a IGD device can be initialized."""
    requester = UpnpTestRequester(RESPONSE_MAP)
    factory = UpnpFactory(requester)
    device = await factory.async_create_device("http://igd:1234/device.xml")
    notify_server = UpnpTestNotifyServer(
        requester=requester,
        source=("192.168.1.2", 8090),
    )
    event_handler = notify_server.event_handler
    profile = IgdDevice(device, event_handler=event_handler)
    assert profile


@pytest.mark.asyncio
async def test_get_total_bytes_received() -> None:
    """Test getting total bytes received."""
    responses = dict(RESPONSE_MAP)
    responses[("POST", "http://igd:1234/WANCommonInterfaceConfig")] = HttpResponse(
        200,
        {},
        read_file("igd/action_WANCIC_GetTotalBytesReceived.xml"),
    )
    requester = UpnpTestRequester(responses)
    factory = UpnpFactory(requester)
    device = await factory.async_create_device("http://igd:1234/device.xml")
    notify_server = UpnpTestNotifyServer(
        requester=requester,
        source=("192.168.1.2", 8090),
    )
    event_handler = notify_server.event_handler
    profile = IgdDevice(device, event_handler=event_handler)
    total_bytes_received = await profile.async_get_total_bytes_received()
    assert total_bytes_received == 1337


@pytest.mark.asyncio
async def test_get_total_packets_received_empty_response() -> None:
    """Test getting total packets received with empty response, for broken (Draytek) device."""
    responses = dict(RESPONSE_MAP)
    responses[("POST", "http://igd:1234/WANCommonInterfaceConfig")] = HttpResponse(
        200,
        {},
        read_file("igd/action_WANCIC_GetTotalPacketsReceived.xml"),
    )
    requester = UpnpTestRequester(responses)
    factory = UpnpFactory(requester)
    device = await factory.async_create_device("http://igd:1234/device.xml")
    notify_server = UpnpTestNotifyServer(
        requester=requester,
        source=("192.168.1.2", 8090),
    )
    event_handler = notify_server.event_handler
    profile = IgdDevice(device, event_handler=event_handler)
    total_bytes_received = await profile.async_get_total_packets_received()
    assert total_bytes_received is None


@pytest.mark.asyncio
async def test_get_status_info_invalid_uptime() -> None:
    """Test getting status info with an invalid uptime response."""
    responses = dict(RESPONSE_MAP)
    responses[("POST", "http://igd:1234/WANIPConnection")] = HttpResponse(
        200,
        {},
        read_file("igd/action_WANIPConnection_GetStatusInfoInvalidUptime.xml"),
    )
    requester = UpnpTestRequester(responses)
    factory = UpnpFactory(requester)
    device = await factory.async_create_device("http://igd:1234/device.xml")
    notify_server = UpnpTestNotifyServer(
        requester=requester,
        source=("192.168.1.2", 8090),
    )
    event_handler = notify_server.event_handler
    profile = IgdDevice(device, event_handler=event_handler)
    status_info = await profile.async_get_status_info()
    assert status_info is None


@pytest.mark.asyncio
async def test_negative_bytes_received_counter() -> None:
    """
    Test getting a negative total bytes received counter.

    Some devices implement the counter as a signed integer (i4),
    which can result in negative values.
    """
    responses = dict(RESPONSE_MAP)
    responses[("POST", "http://igd:1234/WANCommonInterfaceConfig")] = HttpResponse(
        200,
        {},
        read_file("igd/action_WANCIC_GetTotalBytesReceived_i4.xml"),
    )
    requester = UpnpTestRequester(responses)
    factory = UpnpFactory(requester)
    device = await factory.async_create_device("http://igd:1234/device.xml")
    notify_server = UpnpTestNotifyServer(
        requester=requester,
        source=("192.168.1.2", 8090),
    )
    event_handler = notify_server.event_handler
    profile = IgdDevice(device, event_handler=event_handler)
    total_bytes_received = await profile.async_get_total_bytes_received()
    assert total_bytes_received == 1615498126  # 2**31 + -531985522


@pytest.mark.asyncio
async def test_derived_rates_with_uint32_overflow() -> None:
    """Test derived rates with and without uint32 overflow handling."""
    requester = UpnpTestRequester(RESPONSE_MAP)
    factory = UpnpFactory(requester)
    device = await factory.async_create_device("http://igd:1234/device.xml")
    notify_server = UpnpTestNotifyServer(
        requester=requester,
        source=("192.168.1.2", 8090),
    )
    event_handler = notify_server.event_handler

    previous_timestamp = datetime(2000, 1, 1, 0, 0, 0)
    initial_traffic_state = TrafficCounterState(
        timestamp=previous_timestamp,
        bytes_received=2**32 - 100,
        bytes_sent=2**32 - 200,
        packets_received=2**32 - 50,
        packets_sent=2**32 - 1,
        bytes_received_original=2**32 - 100,
        bytes_sent_original=2**32 - 200,
        packets_received_original=2**32 - 50,
        packets_sent_original=2**32 - 1,
    )
    current_traffic_state = TrafficCounterState(
        timestamp=previous_timestamp + timedelta(seconds=10),
        bytes_received=50,
        bytes_sent=25,
        packets_received=10,
        packets_sent=4,
        bytes_received_original=50,
        bytes_sent_original=25,
        packets_received_original=10,
        packets_sent_original=4,
    )
    profile = FixedCounterIgdDevice(
        device,
        event_handler,
        initial_traffic_state=initial_traffic_state,
        current_traffic_state=current_traffic_state,
    )

    state = await profile.async_get_traffic_and_status_data(
        items={
            IgdStateItem.KIBIBYTES_PER_SEC_RECEIVED,
            IgdStateItem.KIBIBYTES_PER_SEC_SENT,
            IgdStateItem.PACKETS_PER_SEC_RECEIVED,
            IgdStateItem.PACKETS_PER_SEC_SENT,
            IgdStateItem.KIBIBYTES_PER_SEC_RECEIVED_UINT32_OVERFLOW,
            IgdStateItem.KIBIBYTES_PER_SEC_SENT_UINT32_OVERFLOW,
            IgdStateItem.PACKETS_PER_SEC_RECEIVED_UINT32_OVERFLOW,
            IgdStateItem.PACKETS_PER_SEC_SENT_UINT32_OVERFLOW,
        },
        force_poll=True,
    )

    assert state.kibibytes_per_sec_received is None
    assert state.kibibytes_per_sec_sent is None
    assert state.packets_per_sec_received is None
    assert state.packets_per_sec_sent is None

    elapsed_seconds = (current_traffic_state.timestamp - initial_traffic_state.timestamp).total_seconds()

    assert state.kibibytes_per_sec_received_uint32_overflow == pytest.approx((150 / 1024) / elapsed_seconds)
    assert state.kibibytes_per_sec_sent_uint32_overflow == pytest.approx((225 / 1024) / elapsed_seconds)
    assert state.packets_per_sec_received_uint32_overflow == pytest.approx(60 / elapsed_seconds)
    assert state.packets_per_sec_sent_uint32_overflow == pytest.approx(5 / elapsed_seconds)
