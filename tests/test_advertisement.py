"""Unit tests for advertisement."""

from unittest.mock import AsyncMock

import pytest

from async_upnp_client.advertisement import SsdpAdvertisementListener
from async_upnp_client.utils import CaseInsensitiveDict

from .common import (
    ADVERTISEMENT_HEADERS_DEFAULT,
    ADVERTISEMENT_REQUEST_LINE,
    SEARCH_HEADERS_DEFAULT,
    SEARCH_REQUEST_LINE,
)


@pytest.mark.asyncio
async def test_receive_ssdp_alive() -> None:
    """Test handling a ssdp:alive advertisement."""
    # pylint: disable=protected-access
    async_on_alive = AsyncMock()
    async_on_byebye = AsyncMock()
    async_on_update = AsyncMock()
    listener = SsdpAdvertisementListener(
        async_on_alive=async_on_alive,
        async_on_byebye=async_on_byebye,
        async_on_update=async_on_update,
    )
    headers = CaseInsensitiveDict(ADVERTISEMENT_HEADERS_DEFAULT)
    headers["NTS"] = "ssdp:alive"
    listener._on_data(ADVERTISEMENT_REQUEST_LINE, headers)

    async_on_alive.assert_called_with(headers)
    async_on_byebye.assert_not_called()
    async_on_update.assert_not_called()


@pytest.mark.asyncio
async def test_receive_ssdp_byebye() -> None:
    """Test handling a ssdp:alive advertisement."""
    # pylint: disable=protected-access
    async_on_alive = AsyncMock()
    async_on_byebye = AsyncMock()
    async_on_update = AsyncMock()
    listener = SsdpAdvertisementListener(
        async_on_alive=async_on_alive,
        async_on_byebye=async_on_byebye,
        async_on_update=async_on_update,
    )
    headers = CaseInsensitiveDict(ADVERTISEMENT_HEADERS_DEFAULT)
    headers["NTS"] = "ssdp:byebye"
    listener._on_data(ADVERTISEMENT_REQUEST_LINE, headers)

    async_on_alive.assert_not_called()
    async_on_byebye.assert_called_with(headers)
    async_on_update.assert_not_called()


@pytest.mark.asyncio
async def test_receive_ssdp_update() -> None:
    """Test handling a ssdp:alive advertisement."""
    # pylint: disable=protected-access
    async_on_alive = AsyncMock()
    async_on_byebye = AsyncMock()
    async_on_update = AsyncMock()
    listener = SsdpAdvertisementListener(
        async_on_alive=async_on_alive,
        async_on_byebye=async_on_byebye,
        async_on_update=async_on_update,
    )
    headers = CaseInsensitiveDict(ADVERTISEMENT_HEADERS_DEFAULT)
    headers["NTS"] = "ssdp:update"
    listener._on_data(ADVERTISEMENT_REQUEST_LINE, headers)

    async_on_alive.assert_not_called()
    async_on_byebye.assert_not_called()
    async_on_update.assert_called_with(headers)


@pytest.mark.asyncio
async def test_receive_ssdp_search_response() -> None:
    """Test handling a ssdp search response, which is ignored."""
    # pylint: disable=protected-access
    async_on_alive = AsyncMock()
    async_on_byebye = AsyncMock()
    async_on_update = AsyncMock()
    listener = SsdpAdvertisementListener(
        async_on_alive=async_on_alive,
        async_on_byebye=async_on_byebye,
        async_on_update=async_on_update,
    )
    headers = CaseInsensitiveDict(SEARCH_HEADERS_DEFAULT)
    listener._on_data(SEARCH_REQUEST_LINE, headers)

    async_on_alive.assert_not_called()
    async_on_byebye.assert_not_called()
    async_on_update.assert_not_called()
