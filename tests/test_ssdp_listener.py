"""Unit tests for ssdp_listener."""

from datetime import datetime, timedelta
from typing import AsyncGenerator
from unittest.mock import patch

try:
    from unittest.mock import AsyncMock
except ImportError:
    # For python 3.6/3.7
    from mock import AsyncMock  # type: ignore

import pytest

from async_upnp_client.advertisement import SsdpAdvertisementListener
from async_upnp_client.const import NotificationSubType, SsdpSource
from async_upnp_client.search import SsdpSearchListener
from async_upnp_client.ssdp_listener import (
    SsdpListener,
    same_headers_differ,
    SsdpDevice,
)
from async_upnp_client.utils import CaseInsensitiveDict

from .common import (
    ADDR,
    ADVERTISEMENT_HEADERS_DEFAULT,
    ADVERTISEMENT_REQUEST_LINE,
    SEARCH_HEADERS_DEFAULT,
    SEARCH_REQUEST_LINE,
)


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
            self._on_search,
            loop=self.loop,
            source=self.source,
            target=self.target,
            timeout=self.search_timeout,
        )
        # await self._search_listener.async_start()

    with patch.object(SsdpListener, "async_start", new=async_start) as mock:
        yield mock


@pytest.mark.asyncio
async def test_see_advertisement_alive() -> None:
    """Test seeing a device through an ssdp:alive-advertisement."""
    # pylint: disable=protected-access
    callback = AsyncMock()
    listener = SsdpListener(async_callback=callback)
    await listener.async_start()
    advertisement_listener = listener._advertisement_listener
    assert advertisement_listener is not None

    # See device for the first time through alive-advertisement.
    headers = CaseInsensitiveDict(ADVERTISEMENT_HEADERS_DEFAULT)
    headers["NTS"] = NotificationSubType.SSDP_ALIVE
    await advertisement_listener._async_on_data(
        ADVERTISEMENT_REQUEST_LINE, headers, ADDR
    )
    callback.assert_awaited()
    assert ADVERTISEMENT_HEADERS_DEFAULT["_udn"] in listener.devices

    # See device for the second time through alive-advertisement, not triggering callback.
    callback.reset_mock()
    headers = CaseInsensitiveDict(ADVERTISEMENT_HEADERS_DEFAULT)
    headers["NTS"] = NotificationSubType.SSDP_ALIVE
    await advertisement_listener._async_on_data(
        ADVERTISEMENT_REQUEST_LINE, headers, ADDR
    )
    callback.assert_not_awaited()
    assert ADVERTISEMENT_HEADERS_DEFAULT["_udn"] in listener.devices

    await listener.async_stop()


@pytest.mark.asyncio
async def test_see_advertisement_byebye() -> None:
    """Test seeing a device through an ssdp:byebye-advertisement."""
    # pylint: disable=protected-access
    callback = AsyncMock()
    listener = SsdpListener(async_callback=callback)
    await listener.async_start()
    advertisement_listener = listener._advertisement_listener
    assert advertisement_listener is not None

    # See device for the first time through byebye-advertisement, not triggering callback.
    callback.reset_mock()
    headers = CaseInsensitiveDict(ADVERTISEMENT_HEADERS_DEFAULT)
    headers["NTS"] = NotificationSubType.SSDP_BYEBYE
    await advertisement_listener._async_on_data(
        ADVERTISEMENT_REQUEST_LINE, headers, ADDR
    )
    callback.assert_not_awaited()
    assert ADVERTISEMENT_HEADERS_DEFAULT["_udn"] not in listener.devices

    # See device for the first time through alive-advertisement, triggering callback.
    callback.reset_mock()
    headers = CaseInsensitiveDict(ADVERTISEMENT_HEADERS_DEFAULT)
    headers["NTS"] = NotificationSubType.SSDP_ALIVE
    await advertisement_listener._async_on_data(
        ADVERTISEMENT_REQUEST_LINE, headers, ADDR
    )
    callback.assert_awaited_once()
    assert callback.await_args is not None
    device, dst, _ = callback.await_args.args
    assert device.combined_headers(dst)["NTS"] == "ssdp:alive"
    assert ADVERTISEMENT_HEADERS_DEFAULT["_udn"] in listener.devices

    # See device for the second time through byebye-advertisement, triggering callback.
    callback.reset_mock()
    headers = CaseInsensitiveDict(ADVERTISEMENT_HEADERS_DEFAULT)
    headers["NTS"] = NotificationSubType.SSDP_BYEBYE
    await advertisement_listener._async_on_data(
        ADVERTISEMENT_REQUEST_LINE, headers, ADDR
    )
    callback.assert_awaited_once()
    assert callback.await_args is not None
    device, dst, _ = callback.await_args.args
    assert device.combined_headers(dst)["NTS"] == "ssdp:byebye"
    assert ADVERTISEMENT_HEADERS_DEFAULT["_udn"] not in listener.devices

    await listener.async_stop()


@pytest.mark.asyncio
async def test_see_advertisement_update() -> None:
    """Test seeing a device through a ssdp:update-advertisement."""
    # pylint: disable=protected-access
    callback = AsyncMock()
    listener = SsdpListener(async_callback=callback)
    await listener.async_start()
    advertisement_listener = listener._advertisement_listener
    assert advertisement_listener is not None

    # See device for the first time through alive-advertisement, triggering callback.
    callback.reset_mock()
    headers = CaseInsensitiveDict(ADVERTISEMENT_HEADERS_DEFAULT)
    headers["NTS"] = NotificationSubType.SSDP_ALIVE
    await advertisement_listener._async_on_data(
        ADVERTISEMENT_REQUEST_LINE, headers, ADDR
    )
    callback.assert_awaited()
    assert ADVERTISEMENT_HEADERS_DEFAULT["_udn"] in listener.devices

    # See device for the second time through update-advertisement, triggering callback.
    callback.reset_mock()
    headers = CaseInsensitiveDict(ADVERTISEMENT_HEADERS_DEFAULT)
    headers["NTS"] = NotificationSubType.SSDP_UPDATE
    headers["BOOTID.UPNP.ORG"] = "2"
    await advertisement_listener._async_on_data(
        ADVERTISEMENT_REQUEST_LINE, headers, ADDR
    )
    callback.assert_awaited()
    assert ADVERTISEMENT_HEADERS_DEFAULT["_udn"] in listener.devices

    await listener.async_stop()


@pytest.mark.asyncio
async def test_see_search() -> None:
    """Test seeing a device through an search."""
    # pylint: disable=protected-access
    callback = AsyncMock()
    listener = SsdpListener(async_callback=callback)
    await listener.async_start()
    search_listener = listener._search_listener
    assert search_listener is not None

    # See device for the first time through search.
    headers = CaseInsensitiveDict(SEARCH_HEADERS_DEFAULT)
    await search_listener._async_on_data(SEARCH_REQUEST_LINE, headers, ADDR)
    callback.assert_awaited()
    assert ADVERTISEMENT_HEADERS_DEFAULT["_udn"] in listener.devices

    await listener.async_stop()


@pytest.mark.asyncio
async def test_see_search_then_alive() -> None:
    """Test seeing a device through a search, then a ssdp:update-advertisement."""
    # pylint: disable=protected-access
    callback = AsyncMock()
    listener = SsdpListener(async_callback=callback)
    await listener.async_start()
    advertisement_listener = listener._advertisement_listener
    assert advertisement_listener is not None
    search_listener = listener._search_listener
    assert search_listener is not None

    # See device for the first time through search.
    headers = CaseInsensitiveDict(SEARCH_HEADERS_DEFAULT)
    await search_listener._async_on_data(SEARCH_REQUEST_LINE, headers, ADDR)
    callback.assert_awaited()
    assert ADVERTISEMENT_HEADERS_DEFAULT["_udn"] in listener.devices

    # See device for the second time through alive-advertisement, not triggering callback.
    callback.reset_mock()
    headers = CaseInsensitiveDict(ADVERTISEMENT_HEADERS_DEFAULT)
    headers["NTS"] = NotificationSubType.SSDP_ALIVE
    await advertisement_listener._async_on_data(
        ADVERTISEMENT_REQUEST_LINE, headers, ADDR
    )
    callback.assert_not_awaited()
    assert ADVERTISEMENT_HEADERS_DEFAULT["_udn"] in listener.devices

    await listener.async_stop()


@pytest.mark.asyncio
async def test_purge_devices() -> None:
    """Test if a device is purged when it times out given the value of the CACHE-CONTROL header."""
    # pylint: disable=protected-access
    callback = AsyncMock()
    listener = SsdpListener(async_callback=callback)
    await listener.async_start()
    search_listener = listener._search_listener
    assert search_listener is not None

    # See device for the first time through alive-advertisement.
    headers = CaseInsensitiveDict(SEARCH_HEADERS_DEFAULT)
    await search_listener._async_on_data(SEARCH_REQUEST_LINE, headers, ADDR)
    callback.assert_awaited()
    assert ADVERTISEMENT_HEADERS_DEFAULT["_udn"] in listener.devices

    # See device for the second time through alive-advertisement.
    headers = CaseInsensitiveDict(SEARCH_HEADERS_DEFAULT)
    await search_listener._async_on_data(SEARCH_REQUEST_LINE, headers, ADDR)
    callback.assert_awaited()
    assert ADVERTISEMENT_HEADERS_DEFAULT["_udn"] in listener.devices

    # "Wait" a bit... and purge devices.
    override_now = headers["_timestamp"] + timedelta(hours=1)
    listener._device_tracker.purge_devices(override_now)
    assert ADVERTISEMENT_HEADERS_DEFAULT["_udn"] not in listener.devices

    # See device for the first time through alive-advertisement.
    headers = CaseInsensitiveDict(SEARCH_HEADERS_DEFAULT)
    await search_listener._async_on_data(SEARCH_REQUEST_LINE, headers, ADDR)
    callback.assert_awaited()
    assert ADVERTISEMENT_HEADERS_DEFAULT["_udn"] in listener.devices

    # "Wait" a bit... and purge devices again.
    override_now = headers["_timestamp"] + timedelta(hours=1)
    listener._device_tracker.purge_devices(override_now)
    assert ADVERTISEMENT_HEADERS_DEFAULT["_udn"] not in listener.devices

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
    callback = AsyncMock()
    listener = SsdpListener(async_callback=callback)
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
    await advertisement_listener._async_on_data(SEARCH_REQUEST_LINE, headers, ADDR)
    callback.assert_not_awaited()

    await listener.async_stop()


@pytest.mark.asyncio
async def test_see_search_invalid_location() -> None:
    """Test headers with invalid location is ignored."""
    # pylint: disable=protected-access
    callback = AsyncMock()
    listener = SsdpListener(async_callback=callback)
    await listener.async_start()
    advertisement_listener = listener._advertisement_listener
    assert advertisement_listener is not None

    # See device for the first time through alive-advertisement.
    headers = CaseInsensitiveDict(SEARCH_HEADERS_DEFAULT)
    headers["location"] = "192.168.1.1"
    await advertisement_listener._async_on_data(SEARCH_REQUEST_LINE, headers, ADDR)
    callback.assert_not_awaited()

    await listener.async_stop()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "location",
    [
        "http://127.0.0.1:1234/device.xml",
        "http://[::1]:1234/device.xml",
    ],
)
async def test_see_search_localhost_location(location: str) -> None:
    """Test localhost location (127.0.0.1/[::1]) is ignored."""
    # pylint: disable=protected-access
    callback = AsyncMock()
    listener = SsdpListener(async_callback=callback)
    await listener.async_start()
    advertisement_listener = listener._advertisement_listener
    assert advertisement_listener is not None

    # See device for the first time through alive-advertisement.
    headers = CaseInsensitiveDict(SEARCH_HEADERS_DEFAULT)
    headers["location"] = location
    await advertisement_listener._async_on_data(SEARCH_REQUEST_LINE, headers, ADDR)
    callback.assert_not_awaited()

    await listener.async_stop()


@pytest.mark.asyncio
async def test_combined_headers() -> None:
    """Test combined headers."""
    # pylint: disable=protected-access
    callback = AsyncMock()
    listener = SsdpListener(async_callback=callback)
    await listener.async_start()
    advertisement_listener = listener._advertisement_listener
    assert advertisement_listener is not None
    search_listener = listener._search_listener
    assert search_listener is not None

    # See device for the first time through search.
    headers = CaseInsensitiveDict(
        {**SEARCH_HEADERS_DEFAULT, "booTID.UPNP.ORG": "0", "Original": "2"}
    )
    await search_listener._async_on_data(SEARCH_REQUEST_LINE, headers)
    callback.assert_awaited()
    assert callback.await_args is not None
    device, dst, _ = callback.await_args.args
    assert ADVERTISEMENT_HEADERS_DEFAULT["_udn"] in listener.devices

    # See device for the second time through alive-advertisement, not triggering callback.
    callback.reset_mock()
    headers = CaseInsensitiveDict(
        {**ADVERTISEMENT_HEADERS_DEFAULT, "BooTID.UPNP.ORG": "2"}
    )
    headers["NTS"] = NotificationSubType.SSDP_ALIVE
    await advertisement_listener._async_on_data(ADVERTISEMENT_REQUEST_LINE, headers)

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
        "nts": "NotificationSubType.SSDP_ALIVE",
        "original": "2",
        "server": "Linux/2.0 UPnP/1.0 async_upnp_client/0.1",
        "st": "urn:schemas-upnp-org:service:WANCommonInterfaceConfig:1",
        "usn": "uuid:...::urn:schemas-upnp-org:service:WANCommonInterfaceConfig:1",
    }
    assert combined["original"] == "2"
    assert combined["bootid.upnp.org"] == "2"

    await listener.async_stop()
