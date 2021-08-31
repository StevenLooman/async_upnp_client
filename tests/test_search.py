"""Unit tests for search."""
# pylint: disable=protected-access

from datetime import datetime

try:
    from unittest.mock import AsyncMock
except ImportError:
    # For python 3.6/3.7
    from mock import AsyncMock  # type: ignore

import pytest

from async_upnp_client.search import SsdpSearchListener
from async_upnp_client.ssdp import SSDP_IP_V4
from async_upnp_client.utils import CaseInsensitiveDict

TEST_REQUEST_LINE = "HTTP/1.1 200 OK"
TEST_HEADERS_DEFAULT = {
    "CACHE-CONTROL": "max-age=1800",
    "ST": "urn:schemas-upnp-org:service:WANCommonInterfaceConfig:1",
    "USN": "uuid:...::urn:schemas-upnp-org:service:WANCommonInterfaceConfig:1",
    "LOCATION": "http://192.168.1.1:80/RootDevice.xml",
    "BOOTID.UPNP.ORG": "1",
    "SERVER": "Linux/2.0 UPnP/1.0 async_upnp_client/0.1",
    "DATE": "Fri, 1 Jan 2021 12:00:00 GMT",
    "_timestamp": datetime(2021, 1, 1, 12, 00),
    "_host": "192.168.1.1",
    "_port": "1900",
    "_udn": "uuid:...:",
}


@pytest.mark.asyncio
async def test_receive_search_response() -> None:
    """Test handling a ssdp search response."""
    # pylint: disable=protected-access
    callback = AsyncMock()
    listener = SsdpSearchListener(async_callback=callback)
    headers = CaseInsensitiveDict(TEST_HEADERS_DEFAULT)
    await listener._async_on_data(TEST_REQUEST_LINE, headers)

    callback.assert_called_with(headers)


def test_create_ssdp_listener_with_alternate_target() -> None:
    """Create a SsdpSearchListener on an alternate target."""
    callback = AsyncMock()
    connect_callback = AsyncMock()

    yeelight_target = (SSDP_IP_V4, 1982)
    yeelight_service_type = "wifi_bulb"
    listener = SsdpSearchListener(
        async_callback=callback,
        async_connect_callback=connect_callback,
        service_type=yeelight_service_type,
        target=yeelight_target,
    )

    assert listener._target == yeelight_target
    assert listener.service_type == yeelight_service_type
    assert listener.async_callback == callback
    assert listener.async_connect_callback == connect_callback


@pytest.mark.asyncio
async def test_receive_ssdp_alive_advertisement() -> None:
    """Test handling a ssdp alive advertisement, which is ignored."""
    callback = AsyncMock()
    listener = SsdpSearchListener(async_callback=callback)
    headers = CaseInsensitiveDict(
        {
            "CACHE-CONTROL": "max-age=1800",
            "NTS": "ssdp:alive",
            "NT": "urn:schemas-upnp-org:service:WANCommonInterfaceConfig:1",
            "USN": "uuid:...::urn:schemas-upnp-org:service:WANCommonInterfaceConfig:1",
            "LOCATION": "http://192.168.1.1:80/RootDevice.xml",
            "BOOTID.UPNP.ORG": "1",
            "SERVER": "Linux/2.0 UPnP/1.0 async_upnp_client/0.1",
            "_timestamp": datetime(2021, 1, 1, 12, 00),
            "_host": "192.168.1.1",
            "_port": "1900",
            "_udn": "uuid:...:",
        }
    )
    await listener._async_on_data("NOTIFY * HTTP/1.1", headers)

    callback.assert_not_called()
