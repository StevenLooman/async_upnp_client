"""Unit tests for search."""
# pylint: disable=protected-access

from unittest.mock import AsyncMock

import pytest

from async_upnp_client.search import SsdpSearchListener
from async_upnp_client.ssdp import SSDP_IP_V4
from async_upnp_client.utils import CaseInsensitiveDict

from .common import (
    ADVERTISEMENT_HEADERS_DEFAULT,
    ADVERTISEMENT_REQUEST_LINE,
    SEARCH_HEADERS_DEFAULT,
    SEARCH_REQUEST_LINE,
)


@pytest.mark.asyncio
async def test_receive_search_response() -> None:
    """Test handling a ssdp search response."""
    # pylint: disable=protected-access
    async_callback = AsyncMock()
    listener = SsdpSearchListener(async_callback=async_callback)
    headers = CaseInsensitiveDict(SEARCH_HEADERS_DEFAULT)
    listener._on_data(SEARCH_REQUEST_LINE, headers)

    async_callback.assert_called_with(headers)


@pytest.mark.asyncio
async def test_create_ssdp_listener_with_alternate_target() -> None:
    """Create a SsdpSearchListener on an alternate target."""
    async_callback = AsyncMock()
    async_connect_callback = AsyncMock()

    yeelight_target = (SSDP_IP_V4, 1982)
    yeelight_service_type = "wifi_bulb"
    listener = SsdpSearchListener(
        async_callback=async_callback,
        async_connect_callback=async_connect_callback,
        search_target=yeelight_service_type,
        target=yeelight_target,
    )

    assert listener.source == ("0.0.0.0", 0)
    assert listener.target == yeelight_target
    assert listener.search_target == yeelight_service_type
    assert listener.async_callback == async_callback
    assert listener.async_connect_callback == async_connect_callback


@pytest.mark.asyncio
async def test_receive_ssdp_alive_advertisement() -> None:
    """Test handling a ssdp alive advertisement, which is ignored."""
    async_callback = AsyncMock()
    listener = SsdpSearchListener(async_callback=async_callback)
    headers = CaseInsensitiveDict(ADVERTISEMENT_HEADERS_DEFAULT)
    listener._on_data(ADVERTISEMENT_REQUEST_LINE, headers)

    async_callback.assert_not_called()
