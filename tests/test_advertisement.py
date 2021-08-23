"""Unit tests for advertisement."""

from datetime import datetime

try:
    from unittest.mock import AsyncMock
except ImportError:
    # For python 3.6/3.7
    from mock import AsyncMock  # type: ignore

import pytest

from async_upnp_client.advertisement import SsdpAdvertisementListener
from async_upnp_client.utils import CaseInsensitiveDict

TEST_REQUEST_LINE = "NOTIFY * HTTP/1.1"
TEST_HEADERS_DEFAULT = {
    "CACHE-CONTROL": "max-age=1800",
    "NTS": "ssdp:alive",
    "NT": "urn:schemas-upnp-org:service:WANCommonInterfaceConfig:1",
    "USN": "uuid:...::urn:schemas-upnp-org:service:WANCommonInterfaceConfig:1",
    "LOCATION": "http://192.168.1.1:80/RootDevice.xml",
    "BOOTID.UPNP.ORG": "1",
    "SERVER": "Linux/2.0 UPnP/1.0 async_upnp_client/0.1",
    # "_timestamp": datetime.fromisoformat("2021-01-01 12:00"),  # Python 3.7+
    "_timestamp": datetime.strptime("2021-01-01 12:00", "%Y-%m-%d %H:%M"),
    "_host": "192.168.1.1",
    "_port": "1900",
}


@pytest.mark.asyncio
async def test_receive_ssdp_alive() -> None:
    """Test handling a ssdp:alive advertisement."""
    # pylint: disable=protected-access
    on_alive = AsyncMock()
    on_byebye = AsyncMock()
    on_update = AsyncMock()
    listener = SsdpAdvertisementListener(
        on_alive=on_alive, on_byebye=on_byebye, on_update=on_update
    )
    headers = CaseInsensitiveDict(**TEST_HEADERS_DEFAULT)
    headers["NTS"] = "ssdp:alive"
    await listener._async_on_data(TEST_REQUEST_LINE, headers)

    on_alive.assert_called_with(headers)
    on_byebye.assert_not_called()
    on_update.assert_not_called()


@pytest.mark.asyncio
async def test_receive_ssdp_byebye() -> None:
    """Test handling a ssdp:alive advertisement."""
    # pylint: disable=protected-access
    on_alive = AsyncMock()
    on_byebye = AsyncMock()
    on_update = AsyncMock()
    listener = SsdpAdvertisementListener(
        on_alive=on_alive, on_byebye=on_byebye, on_update=on_update
    )
    headers = CaseInsensitiveDict(**TEST_HEADERS_DEFAULT)
    headers["NTS"] = "ssdp:byebye"
    await listener._async_on_data(TEST_REQUEST_LINE, headers)

    on_alive.assert_not_called()
    on_byebye.assert_called_with(headers)
    on_update.assert_not_called()


@pytest.mark.asyncio
async def test_receive_ssdp_update() -> None:
    """Test handling a ssdp:alive advertisement."""
    # pylint: disable=protected-access
    on_alive = AsyncMock()
    on_byebye = AsyncMock()
    on_update = AsyncMock()
    listener = SsdpAdvertisementListener(
        on_alive=on_alive, on_byebye=on_byebye, on_update=on_update
    )
    headers = CaseInsensitiveDict(**TEST_HEADERS_DEFAULT)
    headers["NTS"] = "ssdp:update"
    await listener._async_on_data(TEST_REQUEST_LINE, headers)

    on_alive.assert_not_called()
    on_byebye.assert_not_called()
    on_update.assert_called_with(headers)
