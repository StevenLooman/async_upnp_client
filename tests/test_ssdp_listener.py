"""Unit tests for ssdp listener."""

from datetime import datetime, timedelta
from ipaddress import ip_address
from typing import AsyncGenerator
from unittest.mock import patch

try:
    from unittest.mock import AsyncMock
except ImportError:
    # For python 3.6/3.7
    from mock import AsyncMock  # type: ignore

import pytest

from async_upnp_client.advertisement import SsdpAdvertisementListener
from async_upnp_client.const import NotificationSubType
from async_upnp_client.search import SsdpSearchListener
from async_upnp_client.ssdp_listener import SsdpListener
from async_upnp_client.utils import CaseInsensitiveDict

TEST_NOTIFY_REQUEST_LINE = "NOTIFY * HTTP/1.1"
TEST_UDN = "uuid:test_udn"
TEST_SERVICE = "urn:schemas-upnp-org:service:WANCommonInterfaceConfig:1"
TEST_NOTIFY_HEADERS = {
    "CACHE-CONTROL": "max-age=1800",
    "NTS": "ssdp:alive",
    "NT": TEST_SERVICE,
    "USN": TEST_UDN + "::" + TEST_SERVICE,
    "LOCATION": "http://192.168.1.1:80/RootDevice.xml",
    "BOOTID.UPNP.ORG": "1",
    "SERVER": "Linux/2.0 UPnP/1.0 async_upnp_client/0.1",
    "_timestamp": datetime.now(),
    "_host": "192.168.1.1",
    "_port": "1900",
    "_udn": TEST_UDN,
    "_source": "advertisement",
}
TEST_SEARCH_REQUEST_LINE = "HTTP/1.1 200 OK"
TEST_SEARCH_HEADERS = {
    "CACHE-CONTROL": "max-age=1800",
    "ST": TEST_SERVICE,
    "USN": TEST_UDN + "::" + TEST_SERVICE,
    "LOCATION": "http://192.168.1.1:80/RootDevice.xml",
    "BOOTID.UPNP.ORG": "1",
    "SERVER": "Linux/2.0 UPnP/1.0 async_upnp_client/0.1",
    "DATE": "Fri, 1 Jan 2021 12:00:00 GMT",
    "_timestamp": datetime.now(),
    "_host": "192.168.1.1",
    "_port": "1900",
    "_udn": TEST_UDN,
    "_source": "search",
}


@pytest.fixture
async def mock_start_listeners() -> AsyncGenerator:
    """Create listeners but don't call async_start()."""
    # pylint: disable=protected-access

    async def async_start(self: SsdpListener) -> None:
        target_ip = ip_address(self.target[0])
        self._advertisement_listener = SsdpAdvertisementListener(
            on_alive=self._on_alive,
            on_update=self._on_update,
            on_byebye=self._on_byebye,
            source_ip=self.source_ip,
            target_ip=target_ip,
            loop=self.loop,
        )

        self._search_listener = SsdpSearchListener(
            self._on_search,
            loop=self.loop,
            source_ip=self.source_ip,
            target=self.target,
            timeout=self.search_timeout,
        )

    with patch.object(SsdpListener, "async_start", new=async_start) as mock:
        yield mock


@pytest.mark.asyncio
@pytest.mark.usefixtures("mock_start_listeners")
async def test_see_advertisement_alive() -> None:
    """Test seeing a device through an ssdp:alive-advertisement."""
    # pylint: disable=protected-access
    callback = AsyncMock()
    listener = SsdpListener(callback=callback)
    await listener.async_start()
    advertisement_listener = listener._advertisement_listener
    assert advertisement_listener is not None

    # See device for the first time through alive-advertisement.
    headers = CaseInsensitiveDict(**TEST_NOTIFY_HEADERS)
    headers["NTS"] = NotificationSubType.SSDP_ALIVE
    await advertisement_listener._async_on_data(
        request_line=TEST_NOTIFY_REQUEST_LINE, headers=headers
    )
    callback.assert_awaited()
    assert TEST_UDN in listener.devices

    await listener.async_stop()


@pytest.mark.asyncio
@pytest.mark.usefixtures("mock_start_listeners")
async def test_see_advertisement_byebye() -> None:
    """Test seeing a device through an ssdp:byebye-advertisement."""
    # pylint: disable=protected-access
    callback = AsyncMock()
    listener = SsdpListener(callback=callback)
    await listener.async_start()
    advertisement_listener = listener._advertisement_listener
    assert advertisement_listener is not None

    # See device for the first time through byebye-advertisement, not triggering callback.
    callback.reset_mock()
    headers = CaseInsensitiveDict(**TEST_NOTIFY_HEADERS)
    headers["NTS"] = NotificationSubType.SSDP_BYEBYE
    await advertisement_listener._async_on_data(
        request_line=TEST_NOTIFY_REQUEST_LINE, headers=headers
    )
    callback.assert_not_awaited()
    assert TEST_UDN not in listener.devices

    # See device for the first time through alive-advertisement, triggering callback.
    callback.reset_mock()
    headers = CaseInsensitiveDict(**TEST_NOTIFY_HEADERS)
    headers["NTS"] = NotificationSubType.SSDP_ALIVE
    await advertisement_listener._async_on_data(
        request_line=TEST_NOTIFY_REQUEST_LINE, headers=headers
    )
    callback.assert_awaited()
    assert TEST_UDN in listener.devices

    # See device for the second time through byebye-advertisement, triggering callback.
    callback.reset_mock()
    headers = CaseInsensitiveDict(**TEST_NOTIFY_HEADERS)
    headers["NTS"] = NotificationSubType.SSDP_BYEBYE
    await advertisement_listener._async_on_data(
        request_line=TEST_NOTIFY_REQUEST_LINE, headers=headers
    )
    callback.assert_awaited()
    assert TEST_UDN not in listener.devices

    await listener.async_stop()


@pytest.mark.asyncio
@pytest.mark.usefixtures("mock_start_listeners")
async def test_see_advertisement_update() -> None:
    """Test seeing a device through an ssdp:update-advertisement."""
    # pylint: disable=protected-access
    callback = AsyncMock()
    listener = SsdpListener(callback=callback)
    await listener.async_start()
    advertisement_listener = listener._advertisement_listener
    assert advertisement_listener is not None

    # See device for the first time through alive-advertisement, triggering callback.
    callback.reset_mock()
    headers = CaseInsensitiveDict(**TEST_NOTIFY_HEADERS)
    headers["NTS"] = NotificationSubType.SSDP_ALIVE
    await advertisement_listener._async_on_data(
        request_line=TEST_NOTIFY_REQUEST_LINE, headers=headers
    )
    callback.assert_awaited()
    assert TEST_UDN in listener.devices

    # See device for the second time through update-advertisement, triggering callback.
    callback.reset_mock()
    headers = CaseInsensitiveDict(**TEST_NOTIFY_HEADERS)
    headers["NTS"] = NotificationSubType.SSDP_UPDATE
    headers["BOOTID.UPNP.ORG"] = "2"
    await advertisement_listener._async_on_data(
        request_line=TEST_NOTIFY_REQUEST_LINE, headers=headers
    )
    callback.assert_awaited()
    assert TEST_UDN in listener.devices

    await listener.async_stop()


@pytest.mark.asyncio
@pytest.mark.usefixtures("mock_start_listeners")
async def test_see_search() -> None:
    """Test seeing a device through an search."""
    # pylint: disable=protected-access
    callback = AsyncMock()
    listener = SsdpListener(callback=callback)
    await listener.async_start()
    search_listener = listener._search_listener
    assert search_listener is not None

    # See device for the first time through search.
    headers = CaseInsensitiveDict(**TEST_SEARCH_HEADERS)
    await search_listener._async_on_data(
        request_line=TEST_SEARCH_REQUEST_LINE, headers=headers
    )
    callback.assert_awaited()
    assert TEST_UDN in listener.devices

    await listener.async_stop()


@pytest.mark.asyncio
@pytest.mark.usefixtures("mock_start_listeners")
async def test_see_search_then_alive() -> None:
    """Test seeing a device through a search."""
    # pylint: disable=protected-access
    callback = AsyncMock()
    listener = SsdpListener(callback=callback)
    await listener.async_start()
    advertisement_listener = listener._advertisement_listener
    assert advertisement_listener is not None
    search_listener = listener._search_listener
    assert search_listener is not None

    # See device for the first time through search.
    headers = CaseInsensitiveDict(**TEST_SEARCH_HEADERS)
    await search_listener._async_on_data(
        request_line=TEST_SEARCH_REQUEST_LINE, headers=headers
    )
    callback.assert_awaited()
    assert TEST_UDN in listener.devices

    # See device for the second time through alive-advertisement, not triggering callback.
    callback.reset_mock()
    headers = CaseInsensitiveDict(**TEST_NOTIFY_HEADERS)
    headers["NTS"] = NotificationSubType.SSDP_ALIVE
    await advertisement_listener._async_on_data(
        request_line=TEST_NOTIFY_REQUEST_LINE, headers=headers
    )
    callback.assert_not_awaited()
    assert TEST_UDN in listener.devices

    await listener.async_stop()


@pytest.mark.asyncio
@pytest.mark.usefixtures("mock_start_listeners")
async def test_purge_devices() -> None:
    """Test if a device is purged when it times out given the value of the CACHE-CONTROL header."""
    # pylint: disable=protected-access
    callback = AsyncMock()
    listener = SsdpListener(callback=callback)
    await listener.async_start()
    search_listener = listener._search_listener
    assert search_listener is not None

    # See device for the first time through alive-advertisement.
    headers = CaseInsensitiveDict(**TEST_SEARCH_HEADERS)
    await search_listener._async_on_data(
        request_line=TEST_SEARCH_REQUEST_LINE, headers=headers
    )
    callback.assert_awaited()
    assert TEST_UDN in listener.devices

    # "Wait" a bit... and purge devices.
    override_now = datetime.now() + timedelta(hours=1)
    listener._device_tracker.purge_devices(override_now)
    assert TEST_UDN not in listener.devices

    await listener.async_stop()
