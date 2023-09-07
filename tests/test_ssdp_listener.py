"""Unit tests for ssdp_listener."""

import asyncio
from datetime import datetime, timedelta
from typing import AsyncGenerator
from unittest.mock import ANY, AsyncMock, Mock, patch

import pytest

from async_upnp_client.advertisement import SsdpAdvertisementListener
from async_upnp_client.const import NotificationSubType, SsdpSource
from async_upnp_client.search import SsdpSearchListener
from async_upnp_client.ssdp_listener import (
    SsdpDevice,
    SsdpListener,
    same_headers_differ,
)
from async_upnp_client.utils import CaseInsensitiveDict

from .common import (
    ADVERTISEMENT_HEADERS_DEFAULT,
    ADVERTISEMENT_REQUEST_LINE,
    SEARCH_HEADERS_DEFAULT,
    SEARCH_REQUEST_LINE,
)

UDN = ADVERTISEMENT_HEADERS_DEFAULT["_udn"]


@pytest.fixture(autouse=True)
async def mock_start_listeners() -> AsyncGenerator:
    """Create listeners but don't call async_start()."""
    # pylint: disable=protected-access

    async def async_start(self: SsdpListener) -> None:
        self._advertisement_listener = SsdpAdvertisementListener(
            on_alive=self._on_alive,
            on_update=self._on_update,
            on_byebye=self._on_byebye,
            source=self.source,
            target=self.target,
            loop=self.loop,
        )
        # await self._advertisement_listener.async_start()

        self._search_listener = SsdpSearchListener(
            callback=self._on_search,
            loop=self.loop,
            source=self.source,
            target=self.target,
            timeout=self.search_timeout,
        )
        # await self._search_listener.async_start()

    with patch.object(SsdpListener, "async_start", new=async_start) as mock:
        yield mock


async def see_advertisement(
    ssdp_listener: SsdpListener, request_line: str, headers: CaseInsensitiveDict
) -> None:
    """See advertisement."""
    # pylint: disable=protected-access
    advertisement_listener = ssdp_listener._advertisement_listener
    assert advertisement_listener is not None
    advertisement_listener._on_data(request_line, headers)
    await asyncio.sleep(0)  # Allow callback to run, if called.


async def see_search(
    ssdp_listener: SsdpListener, request_line: str, headers: CaseInsensitiveDict
) -> None:
    """See search."""
    # pylint: disable=protected-access
    search_listener = ssdp_listener._search_listener
    assert search_listener is not None
    search_listener._on_data(request_line, headers)
    await asyncio.sleep(0)  # Allow callback to run, if called.


@pytest.mark.asyncio
async def test_see_advertisement_alive() -> None:
    """Test seeing a device through an ssdp:alive-advertisement."""
    # pylint: disable=protected-access
    async_callback = AsyncMock()
    listener = SsdpListener(async_callback=async_callback)
    await listener.async_start()

    # See device for the first time through alive-advertisement.
    async_callback.reset_mock()
    headers = CaseInsensitiveDict(ADVERTISEMENT_HEADERS_DEFAULT)
    headers["NTS"] = "ssdp:alive"
    await see_advertisement(listener, ADVERTISEMENT_REQUEST_LINE, headers)
    async_callback.assert_awaited_once_with(
        ANY,
        "urn:schemas-upnp-org:service:WANCommonInterfaceConfig:1",
        SsdpSource.ADVERTISEMENT_ALIVE,
    )
    assert UDN in listener.devices
    assert listener.devices[UDN].location is not None

    # See device for the second time through alive-advertisement, not triggering callback.
    async_callback.reset_mock()
    headers = CaseInsensitiveDict(ADVERTISEMENT_HEADERS_DEFAULT)
    headers["NTS"] = "ssdp:alive"
    await see_advertisement(listener, ADVERTISEMENT_REQUEST_LINE, headers)
    async_callback.assert_not_awaited()
    assert UDN in listener.devices
    assert listener.devices[UDN].location is not None

    await listener.async_stop()


@pytest.mark.asyncio
async def test_see_advertisement_byebye() -> None:
    """Test seeing a device through an ssdp:byebye-advertisement."""
    # pylint: disable=protected-access
    async_callback = AsyncMock()
    listener = SsdpListener(async_callback=async_callback)
    await listener.async_start()

    # See device for the first time through byebye-advertisement, not triggering callback.
    async_callback.reset_mock()
    headers = CaseInsensitiveDict(ADVERTISEMENT_HEADERS_DEFAULT)
    headers["NTS"] = "ssdp:byebye"
    await see_advertisement(listener, ADVERTISEMENT_REQUEST_LINE, headers)
    async_callback.assert_not_awaited()
    assert UDN not in listener.devices

    # See device for the first time through alive-advertisement, triggering callback.
    async_callback.reset_mock()
    headers = CaseInsensitiveDict(ADVERTISEMENT_HEADERS_DEFAULT)
    headers["NTS"] = "ssdp:alive"
    await see_advertisement(listener, ADVERTISEMENT_REQUEST_LINE, headers)
    async_callback.assert_awaited_once_with(
        ANY,
        "urn:schemas-upnp-org:service:WANCommonInterfaceConfig:1",
        SsdpSource.ADVERTISEMENT_ALIVE,
    )
    assert async_callback.await_args is not None
    device, dst, _ = async_callback.await_args.args
    assert device.combined_headers(dst)["NTS"] == NotificationSubType.SSDP_ALIVE
    assert UDN in listener.devices
    assert listener.devices[UDN].location is not None

    # See device for the second time through byebye-advertisement, triggering callback.
    async_callback.reset_mock()
    headers = CaseInsensitiveDict(ADVERTISEMENT_HEADERS_DEFAULT)
    headers["NTS"] = "ssdp:byebye"
    await see_advertisement(listener, ADVERTISEMENT_REQUEST_LINE, headers)
    async_callback.assert_awaited_once_with(
        ANY,
        "urn:schemas-upnp-org:service:WANCommonInterfaceConfig:1",
        SsdpSource.ADVERTISEMENT_BYEBYE,
    )
    assert async_callback.await_args is not None
    device, dst, _ = async_callback.await_args.args
    assert device.combined_headers(dst)["NTS"] == NotificationSubType.SSDP_BYEBYE
    assert UDN not in listener.devices

    await listener.async_stop()


@pytest.mark.asyncio
async def test_see_advertisement_update() -> None:
    """Test seeing a device through a ssdp:update-advertisement."""
    # pylint: disable=protected-access
    async_callback = AsyncMock()
    listener = SsdpListener(async_callback=async_callback)
    await listener.async_start()

    # See device for the first time through alive-advertisement, triggering callback.
    async_callback.reset_mock()
    headers = CaseInsensitiveDict(ADVERTISEMENT_HEADERS_DEFAULT)
    headers["NTS"] = "ssdp:alive"
    await see_advertisement(listener, ADVERTISEMENT_REQUEST_LINE, headers)
    async_callback.assert_awaited_once_with(
        ANY,
        "urn:schemas-upnp-org:service:WANCommonInterfaceConfig:1",
        SsdpSource.ADVERTISEMENT_ALIVE,
    )
    assert UDN in listener.devices
    assert listener.devices[UDN].location is not None

    # See device for the second time through update-advertisement, triggering callback.
    async_callback.reset_mock()
    headers = CaseInsensitiveDict(ADVERTISEMENT_HEADERS_DEFAULT)
    headers["NTS"] = "ssdp:update"
    headers["BOOTID.UPNP.ORG"] = "2"
    await see_advertisement(listener, ADVERTISEMENT_REQUEST_LINE, headers)
    async_callback.assert_awaited_once_with(
        ANY,
        "urn:schemas-upnp-org:service:WANCommonInterfaceConfig:1",
        SsdpSource.ADVERTISEMENT_UPDATE,
    )
    assert UDN in listener.devices
    assert listener.devices[UDN].location is not None

    await listener.async_stop()


@pytest.mark.asyncio
async def test_see_search() -> None:
    """Test seeing a device through an search."""
    # pylint: disable=protected-access
    async_callback = AsyncMock()
    listener = SsdpListener(async_callback=async_callback)
    await listener.async_start()

    # See device for the first time through search.
    async_callback.reset_mock()
    headers = CaseInsensitiveDict(SEARCH_HEADERS_DEFAULT)
    await see_search(listener, SEARCH_REQUEST_LINE, headers)
    async_callback.assert_awaited_once_with(
        ANY,
        "urn:schemas-upnp-org:service:WANCommonInterfaceConfig:1",
        SsdpSource.SEARCH_CHANGED,
    )
    assert UDN in listener.devices
    assert listener.devices[UDN].location is not None

    # See same device again through search, not triggering a change.
    async_callback.reset_mock()
    headers = CaseInsensitiveDict(SEARCH_HEADERS_DEFAULT)
    await see_search(listener, SEARCH_REQUEST_LINE, headers)
    async_callback.assert_awaited_once_with(
        ANY,
        "urn:schemas-upnp-org:service:WANCommonInterfaceConfig:1",
        SsdpSource.SEARCH_ALIVE,
    )
    assert UDN in listener.devices
    assert listener.devices[UDN].location is not None

    await listener.async_stop()


@pytest.mark.asyncio
async def test_see_search_sync() -> None:
    """Test seeing a device through an search."""
    # pylint: disable=protected-access
    callback = Mock()
    listener = SsdpListener(callback=callback)
    await listener.async_start()

    # See device for the first time through search.
    callback.reset_mock()
    headers = CaseInsensitiveDict(SEARCH_HEADERS_DEFAULT)
    await see_search(listener, SEARCH_REQUEST_LINE, headers)
    callback.assert_called_with(
        ANY,
        "urn:schemas-upnp-org:service:WANCommonInterfaceConfig:1",
        SsdpSource.SEARCH_CHANGED,
    )
    assert UDN in listener.devices
    assert listener.devices[UDN].location is not None

    # See same device again through search, not triggering a change.
    callback.reset_mock()
    headers = CaseInsensitiveDict(SEARCH_HEADERS_DEFAULT)
    await see_search(listener, SEARCH_REQUEST_LINE, headers)
    callback.assert_called_with(
        ANY,
        "urn:schemas-upnp-org:service:WANCommonInterfaceConfig:1",
        SsdpSource.SEARCH_ALIVE,
    )
    assert UDN in listener.devices
    assert listener.devices[UDN].location is not None

    await listener.async_stop()


@pytest.mark.asyncio
async def test_see_search_then_alive() -> None:
    """Test seeing a device through a search, then a ssdp:alive-advertisement."""
    # pylint: disable=protected-access
    async_callback = AsyncMock()
    listener = SsdpListener(async_callback=async_callback)
    await listener.async_start()

    # See device for the first time through search.
    async_callback.reset_mock()
    headers = CaseInsensitiveDict(SEARCH_HEADERS_DEFAULT)
    await see_search(listener, SEARCH_REQUEST_LINE, headers)
    async_callback.assert_awaited_once_with(
        ANY,
        "urn:schemas-upnp-org:service:WANCommonInterfaceConfig:1",
        SsdpSource.SEARCH_CHANGED,
    )
    assert UDN in listener.devices
    assert listener.devices[UDN].location is not None

    # See device for the second time through alive-advertisement, not triggering callback.
    async_callback.reset_mock()
    headers = CaseInsensitiveDict(ADVERTISEMENT_HEADERS_DEFAULT)
    headers["NTS"] = "ssdp:alive"
    await see_advertisement(listener, ADVERTISEMENT_REQUEST_LINE, headers)
    async_callback.assert_not_awaited()
    assert UDN in listener.devices
    assert listener.devices[UDN].location is not None

    await listener.async_stop()


@pytest.mark.asyncio
async def test_see_search_then_update() -> None:
    """Test seeing a device through a search, then a ssdp:update-advertisement."""
    # pylint: disable=protected-access
    async_callback = AsyncMock()
    listener = SsdpListener(async_callback=async_callback)
    await listener.async_start()

    # See device for the first time through search.
    async_callback.reset_mock()
    headers = CaseInsensitiveDict(SEARCH_HEADERS_DEFAULT)
    await see_search(listener, SEARCH_REQUEST_LINE, headers)
    async_callback.assert_awaited_once_with(
        ANY,
        "urn:schemas-upnp-org:service:WANCommonInterfaceConfig:1",
        SsdpSource.SEARCH_CHANGED,
    )
    assert UDN in listener.devices
    assert listener.devices[UDN].location is not None

    # See device for the second time through update-advertisement, triggering callback.
    async_callback.reset_mock()
    headers = CaseInsensitiveDict(ADVERTISEMENT_HEADERS_DEFAULT)
    headers["NTS"] = "ssdp:update"
    await see_advertisement(listener, ADVERTISEMENT_REQUEST_LINE, headers)
    async_callback.assert_awaited_once_with(
        ANY,
        "urn:schemas-upnp-org:service:WANCommonInterfaceConfig:1",
        SsdpSource.ADVERTISEMENT_UPDATE,
    )
    assert UDN in listener.devices
    assert listener.devices[UDN].location is not None

    await listener.async_stop()


@pytest.mark.asyncio
async def test_see_search_then_byebye() -> None:
    """Test seeing a device through a search, then a ssdp:byebye-advertisement."""
    # pylint: disable=protected-access
    async_callback = AsyncMock()
    listener = SsdpListener(async_callback=async_callback)
    await listener.async_start()

    # See device for the first time through search.
    async_callback.reset_mock()
    headers = CaseInsensitiveDict(SEARCH_HEADERS_DEFAULT)
    await see_search(listener, SEARCH_REQUEST_LINE, headers)
    async_callback.assert_awaited_once_with(
        ANY,
        "urn:schemas-upnp-org:service:WANCommonInterfaceConfig:1",
        SsdpSource.SEARCH_CHANGED,
    )
    assert UDN in listener.devices
    assert listener.devices[UDN].location is not None

    # See device for the second time through byebye-advertisement,
    # triggering byebye-callback and device removed.
    async_callback.reset_mock()
    headers = CaseInsensitiveDict(ADVERTISEMENT_HEADERS_DEFAULT)
    headers["NTS"] = "ssdp:byebye"
    await see_advertisement(listener, ADVERTISEMENT_REQUEST_LINE, headers)
    async_callback.assert_awaited_once_with(
        ANY,
        "urn:schemas-upnp-org:service:WANCommonInterfaceConfig:1",
        SsdpSource.ADVERTISEMENT_BYEBYE,
    )
    assert UDN not in listener.devices

    await listener.async_stop()


@pytest.mark.asyncio
async def test_see_search_then_byebye_then_alive() -> None:
    """Test seeing a device by search, then ssdp:byebye, then ssdp:alive."""
    # pylint: disable=protected-access
    async_callback = AsyncMock()
    listener = SsdpListener(async_callback=async_callback)
    await listener.async_start()

    # See device for the first time through search.
    async_callback.reset_mock()
    headers = CaseInsensitiveDict(SEARCH_HEADERS_DEFAULT)
    await see_search(listener, SEARCH_REQUEST_LINE, headers)
    async_callback.assert_awaited_once_with(
        ANY,
        "urn:schemas-upnp-org:service:WANCommonInterfaceConfig:1",
        SsdpSource.SEARCH_CHANGED,
    )
    assert UDN in listener.devices
    assert listener.devices[UDN].location is not None

    # See device for the second time through byebye-advertisement,
    # triggering byebye-callback and device removed.
    async_callback.reset_mock()
    headers = CaseInsensitiveDict(ADVERTISEMENT_HEADERS_DEFAULT)
    headers["NTS"] = "ssdp:byebye"
    headers["LOCATION"] = ""
    await see_advertisement(listener, ADVERTISEMENT_REQUEST_LINE, headers)
    async_callback.assert_awaited_once_with(
        ANY,
        "urn:schemas-upnp-org:service:WANCommonInterfaceConfig:1",
        SsdpSource.ADVERTISEMENT_BYEBYE,
    )
    assert UDN not in listener.devices

    # See device for the second time through alive-advertisement, not triggering callback.
    async_callback.reset_mock()
    headers = CaseInsensitiveDict(ADVERTISEMENT_HEADERS_DEFAULT)
    headers["NTS"] = "ssdp:alive"
    await see_advertisement(listener, ADVERTISEMENT_REQUEST_LINE, headers)
    async_callback.assert_awaited_once_with(
        ANY,
        "urn:schemas-upnp-org:service:WANCommonInterfaceConfig:1",
        SsdpSource.ADVERTISEMENT_ALIVE,
    )
    assert UDN in listener.devices
    assert listener.devices[UDN].location is not None

    await listener.async_stop()


@pytest.mark.asyncio
async def test_purge_devices() -> None:
    """Test if a device is purged when it times out given the value of the CACHE-CONTROL header."""
    # pylint: disable=protected-access
    async_callback = AsyncMock()
    listener = SsdpListener(async_callback=async_callback)
    await listener.async_start()

    # See device through search.
    async_callback.reset_mock()
    headers = CaseInsensitiveDict(SEARCH_HEADERS_DEFAULT)
    await see_search(listener, SEARCH_REQUEST_LINE, headers)
    async_callback.assert_awaited_once_with(
        ANY,
        "urn:schemas-upnp-org:service:WANCommonInterfaceConfig:1",
        SsdpSource.SEARCH_CHANGED,
    )
    assert UDN in listener.devices
    assert listener.devices[UDN].location is not None

    # "Wait" a bit... and purge devices.
    override_now = headers["_timestamp"] + timedelta(hours=1)
    listener._device_tracker.purge_devices(override_now)
    assert UDN not in listener.devices

    await listener.async_stop()


@pytest.mark.asyncio
async def test_purge_devices_2() -> None:
    """Test if a device is purged when it times out, part 2."""
    # pylint: disable=protected-access
    async_callback = AsyncMock()
    listener = SsdpListener(async_callback=async_callback)
    await listener.async_start()

    # See device through search.
    async_callback.reset_mock()
    headers = CaseInsensitiveDict(SEARCH_HEADERS_DEFAULT)
    await see_search(listener, SEARCH_REQUEST_LINE, headers)
    async_callback.assert_awaited_once_with(
        ANY,
        "urn:schemas-upnp-org:service:WANCommonInterfaceConfig:1",
        SsdpSource.SEARCH_CHANGED,
    )
    assert UDN in listener.devices
    assert listener.devices[UDN].location is not None

    # See anotherdevice through search.
    async_callback.reset_mock()
    udn2 = "uuid:device_2"
    new_timestamp = SEARCH_HEADERS_DEFAULT["_timestamp"] + timedelta(hours=1)
    device_2_headers = CaseInsensitiveDict(
        {
            **SEARCH_HEADERS_DEFAULT,
            "USN": udn2 + "::urn:schemas-upnp-org:service:WANCommonInterfaceConfig:2",
            "ST": "urn:schemas-upnp-org:service:WANCommonInterfaceConfig:2",
            "_udn": udn2,
            "_timestamp": new_timestamp,
        }
    )
    await see_search(listener, SEARCH_REQUEST_LINE, device_2_headers)
    async_callback.assert_awaited_once_with(
        ANY,
        "urn:schemas-upnp-org:service:WANCommonInterfaceConfig:2",
        SsdpSource.SEARCH_CHANGED,
    )
    assert UDN not in listener.devices
    assert udn2 in listener.devices
    assert listener.devices[udn2].location is not None

    await listener.async_stop()


def test_same_headers_differ_profile() -> None:
    """Test same_headers_differ."""
    current_headers = CaseInsensitiveDict(
        {
            "Cache-Control": "max-age=1900",
            "location": "http://192.168.1.1:80/RootDevice.xml",
            "Server": "UPnP/1.0 UPnP/1.0 UPnP-Device-Host/1.0",
            "ST": "urn:schemas-upnp-org:device:WANDevice:1",
            "USN": "uuid:upnp-WANDevice-1_0-123456789abc::urn:schemas-upnp-org:device:WANDevice:1",
            "EXT": "",
            "_location_original": "http://192.168.1.1:80/RootDevice.xml",
            "_timestamp": datetime.now(),
            "_host": "192.168.1.1",
            "_port": "1900",
            "_udn": "uuid:upnp-WANDevice-1_0-123456789abc",
            "_source": SsdpSource.SEARCH,
        }
    )
    new_headers = CaseInsensitiveDict(
        {
            "Cache-Control": "max-age=1900",
            "location": "http://192.168.1.1:80/RootDevice.xml",
            "Server": "UPnP/1.0 UPnP/1.0 UPnP-Device-Host/1.0 abc",
            "Date": "Sat, 11 Sep 2021 12:00:00 GMT",
            "ST": "urn:schemas-upnp-org:device:WANDevice:1",
            "USN": "uuid:upnp-WANDevice-1_0-123456789abc::urn:schemas-upnp-org:device:WANDevice:1",
            "EXT": "",
            "_location_original": "http://192.168.1.1:80/RootDevice.xml",
            "_timestamp": datetime.now(),
            "_host": "192.168.1.1",
            "_port": "1900",
            "_udn": "uuid:upnp-WANDevice-1_0-123456789abc",
            "_source": SsdpSource.SEARCH,
        }
    )
    for _ in range(0, 10000):
        assert not same_headers_differ(current_headers, new_headers)


@pytest.mark.asyncio
async def test_see_search_invalid_usn() -> None:
    """Test invalid USN is ignored."""
    # pylint: disable=protected-access
    async_callback = AsyncMock()
    listener = SsdpListener(async_callback=async_callback)
    await listener.async_start()
    advertisement_listener = listener._advertisement_listener
    assert advertisement_listener is not None

    # See device for the first time through alive-advertisement.
    headers = CaseInsensitiveDict(SEARCH_HEADERS_DEFAULT)
    headers[
        "ST"
    ] = "urn:Microsoft Windows Peer Name Resolution Protocol: V4:IPV6:LinkLocal"
    headers["USN"] = "[fe80::aaaa:bbbb:cccc:dddd]:3540"
    del headers["_udn"]
    advertisement_listener._on_data(SEARCH_REQUEST_LINE, headers)
    async_callback.assert_not_awaited()

    await listener.async_stop()


@pytest.mark.asyncio
async def test_see_search_invalid_location() -> None:
    """Test headers with invalid location is ignored."""
    # pylint: disable=protected-access
    async_callback = AsyncMock()
    listener = SsdpListener(async_callback=async_callback)
    await listener.async_start()
    advertisement_listener = listener._advertisement_listener
    assert advertisement_listener is not None

    # See device for the first time through alive-advertisement.
    async_callback.reset_mock()
    headers = CaseInsensitiveDict(SEARCH_HEADERS_DEFAULT)
    headers["location"] = "192.168.1.1"
    advertisement_listener._on_data(SEARCH_REQUEST_LINE, headers)
    async_callback.assert_not_awaited()

    await listener.async_stop()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "location",
    [
        "http://127.0.0.1:1234/device.xml",
        "http://[::1]:1234/device.xml",
        "http://169.254.12.1:1234/device.xml",
    ],
)
async def test_see_search_localhost_location(location: str) -> None:
    """Test localhost location (127.0.0.1/[::1]) is ignored."""
    # pylint: disable=protected-access
    async_callback = AsyncMock()
    listener = SsdpListener(async_callback=async_callback)
    await listener.async_start()
    advertisement_listener = listener._advertisement_listener
    assert advertisement_listener is not None

    # See device for the first time through alive-advertisement.
    async_callback.reset_mock()
    headers = CaseInsensitiveDict(SEARCH_HEADERS_DEFAULT)
    headers["location"] = location
    advertisement_listener._on_data(SEARCH_REQUEST_LINE, headers)
    async_callback.assert_not_awaited()

    await listener.async_stop()


@pytest.mark.asyncio
async def test_combined_headers() -> None:
    """Test combined headers."""
    # pylint: disable=protected-access
    async_callback = AsyncMock()
    listener = SsdpListener(async_callback=async_callback)
    await listener.async_start()

    # See device for the first time through search.
    async_callback.reset_mock()
    headers = CaseInsensitiveDict(
        {**SEARCH_HEADERS_DEFAULT, "booTID.UPNP.ORG": "0", "Original": "2"}
    )
    await see_search(listener, SEARCH_REQUEST_LINE, headers)
    async_callback.assert_awaited_once_with(
        ANY,
        "urn:schemas-upnp-org:service:WANCommonInterfaceConfig:1",
        SsdpSource.SEARCH_CHANGED,
    )
    assert async_callback.await_args is not None
    device, dst, _ = async_callback.await_args.args
    assert UDN in listener.devices
    assert listener.devices[UDN].location is not None

    # See device for the second time through alive-advertisement, not triggering callback.
    async_callback.reset_mock()
    headers = CaseInsensitiveDict(
        {**ADVERTISEMENT_HEADERS_DEFAULT, "BooTID.UPNP.ORG": "2"}
    )
    headers["NTS"] = "ssdp:alive"
    await see_advertisement(listener, ADVERTISEMENT_REQUEST_LINE, headers)

    assert isinstance(device, SsdpDevice)
    combined = device.combined_headers(dst)
    assert isinstance(combined, CaseInsensitiveDict)
    result = {k.lower(): str(v) for k, v in combined.as_dict().items()}
    del result["_timestamp"]
    assert result == {
        "_host": "192.168.1.1",
        "_port": "1900",
        "_udn": "uuid:...",
        "bootid.upnp.org": "2",
        "cache-control": "max-age=1800",
        "date": "Fri, 1 Jan 2021 12:00:00 GMT",
        "location": "http://192.168.1.1:80/RootDevice.xml",
        "nt": "urn:schemas-upnp-org:service:WANCommonInterfaceConfig:1",
        "nts": NotificationSubType.SSDP_ALIVE,
        "original": "2",
        "server": "Linux/2.0 UPnP/1.0 async_upnp_client/0.1",
        "st": "urn:schemas-upnp-org:service:WANCommonInterfaceConfig:1",
        "usn": "uuid:...::urn:schemas-upnp-org:service:WANCommonInterfaceConfig:1",
    }
    assert combined["original"] == "2"
    assert combined["bootid.upnp.org"] == "2"
    assert "_source" not in combined

    headers = CaseInsensitiveDict(
        {
            **ADVERTISEMENT_HEADERS_DEFAULT,
            "BooTID.UPNP.ORG": "2",
            "st": "urn:schemas-upnp-org:service:WANCommonInterfaceConfig:2",
        }
    )
    headers["NTS"] = "ssdp:alive"
    await see_advertisement(listener, ADVERTISEMENT_REQUEST_LINE, headers)
    combined = device.combined_headers(dst)
    assert combined["st"] == "urn:schemas-upnp-org:service:WANCommonInterfaceConfig:2"
    await listener.async_stop()


@pytest.mark.asyncio
async def test_see_search_device_ipv4_and_ipv6() -> None:
    """Test seeing the same device via IPv4, then via IPv6."""
    # pylint: disable=protected-access
    async_callback = AsyncMock()
    listener = SsdpListener(async_callback=async_callback)
    await listener.async_start()

    # See device via IPv4, callback should be called.
    async_callback.reset_mock()
    location_ipv4 = "http://192.168.1.1:80/RootDevice.xml"
    headers = CaseInsensitiveDict(
        {
            **SEARCH_HEADERS_DEFAULT,
            "LOCATION": location_ipv4,
        }
    )
    await see_search(listener, SEARCH_REQUEST_LINE, headers)
    async_callback.assert_awaited_once_with(
        ANY, SEARCH_HEADERS_DEFAULT["ST"], SsdpSource.SEARCH_CHANGED
    )

    # See device via IPv6, callback should be called with SsdpSource.SEARCH_ALIVE,
    # not SEARCH_UPDATE.
    async_callback.reset_mock()
    location_ipv6 = "http://[fe80::1]:80/RootDevice.xml"
    headers = CaseInsensitiveDict(
        {
            **SEARCH_HEADERS_DEFAULT,
            "LOCATION": location_ipv6,
        }
    )
    await see_search(listener, SEARCH_REQUEST_LINE, headers)
    async_callback.assert_awaited_once_with(
        ANY, SEARCH_HEADERS_DEFAULT["ST"], SsdpSource.SEARCH_ALIVE
    )

    assert listener.devices[SEARCH_HEADERS_DEFAULT["_udn"]].locations
