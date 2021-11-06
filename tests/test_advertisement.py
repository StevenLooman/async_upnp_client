"""Unit tests for advertisement."""

try:
    from unittest.mock import AsyncMock
except ImportError:
    # For python 3.6/3.7
    from mock import AsyncMock  # type: ignore

import pytest

from async_upnp_client.advertisement import SsdpAdvertisementListener
from async_upnp_client.utils import CaseInsensitiveDict

from .common import (
    ADDR,
    ADVERTISEMENT_HEADERS_DEFAULT,
    ADVERTISEMENT_REQUEST_LINE,
    SEARCH_HEADERS_DEFAULT,
    SEARCH_REQUEST_LINE,
)


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
    headers = CaseInsensitiveDict(ADVERTISEMENT_HEADERS_DEFAULT)
    headers["NTS"] = "ssdp:alive"
    await listener._async_on_data(ADVERTISEMENT_REQUEST_LINE, headers, ADDR)

    on_alive.assert_called_with(headers, ADDR)
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
    headers = CaseInsensitiveDict(ADVERTISEMENT_HEADERS_DEFAULT)
    headers["NTS"] = "ssdp:byebye"
    await listener._async_on_data(ADVERTISEMENT_REQUEST_LINE, headers, ADDR)

    on_alive.assert_not_called()
    on_byebye.assert_called_with(headers, ADDR)
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
    headers = CaseInsensitiveDict(ADVERTISEMENT_HEADERS_DEFAULT)
    headers["NTS"] = "ssdp:update"
    await listener._async_on_data(ADVERTISEMENT_REQUEST_LINE, headers, ADDR)

    on_alive.assert_not_called()
    on_byebye.assert_not_called()
    on_update.assert_called_with(headers, ADDR)


@pytest.mark.asyncio
async def test_receive_ssdp_search_response() -> None:
    """Test handling a ssdp search response, which is ignored."""
    # pylint: disable=protected-access
    on_alive = AsyncMock()
    on_byebye = AsyncMock()
    on_update = AsyncMock()
    listener = SsdpAdvertisementListener(
        on_alive=on_alive, on_byebye=on_byebye, on_update=on_update
    )
    headers = CaseInsensitiveDict(SEARCH_HEADERS_DEFAULT)
    await listener._async_on_data(SEARCH_REQUEST_LINE, headers, ADDR)

    on_alive.assert_not_called()
    on_byebye.assert_not_called()
    on_update.assert_not_called()
