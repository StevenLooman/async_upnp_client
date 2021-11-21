"""Unit tests for aiohttp."""

from unittest.mock import ANY, AsyncMock, MagicMock, patch

import pytest

from async_upnp_client.aiohttp import AiohttpNotifyServer, AiohttpRequester
from async_upnp_client.exceptions import UpnpCommunicationError

from .conftest import RESPONSE_MAP, UpnpTestRequester


def test_server_init() -> None:
    """Test initialization of an AiohttpNotifyServer."""
    requester = UpnpTestRequester(RESPONSE_MAP)
    server = AiohttpNotifyServer(requester, ("192.168.1.2", 8000))
    assert server.event_handler is not None


@pytest.mark.asyncio
async def test_server_start() -> None:
    """Test start_server creates internal servers on appropriate addresses."""
    requester = UpnpTestRequester(RESPONSE_MAP)

    mock_socket = MagicMock()
    mock_socket.getsockname.return_value = ("192.168.1.2", 8000)
    mock_server = AsyncMock()
    mock_server.sockets = (mock_socket,)
    mock_loop = AsyncMock()
    mock_loop.create_server.return_value = mock_server

    mock_loop.create_server.reset_mock()
    mock_socket.getsockname.reset_mock()
    server = AiohttpNotifyServer(requester, ("192.168.1.2", 8000), loop=mock_loop)
    await server.start_server()
    mock_loop.create_server.assert_awaited_once_with(ANY, "192.168.1.2", 8000)
    mock_socket.getsockname.assert_called_once()
    assert server.callback_url == "http://192.168.1.2:8000/notify"

    mock_loop.create_server.reset_mock()
    mock_socket.getsockname.reset_mock()
    server = AiohttpNotifyServer(requester, ("0.0.0.0", 8000), loop=mock_loop)
    await server.start_server()
    mock_loop.create_server.assert_awaited_once_with(ANY, "0.0.0.0", 8000)
    mock_socket.getsockname.assert_called_once()
    assert server.callback_url == "http://192.168.1.2:8000/notify"


@pytest.mark.asyncio
async def test_server_stop() -> None:
    """Test stop_server deletes internal servers."""
    requester = UpnpTestRequester(RESPONSE_MAP)
    server = AiohttpNotifyServer(requester, ("0.0.0.0", 0))
    await server.start_server()
    await server.stop_server()
    assert server.event_handler is not None


@pytest.mark.asyncio
@patch(
    "async_upnp_client.aiohttp.aiohttp.ClientSession.request",
    side_effect=UnicodeDecodeError("", b"", 0, 1, ""),
)
async def test_client_decode_error(_mock_request: MagicMock) -> None:
    """Test handling unicode decode error."""
    requester = AiohttpRequester()
    with pytest.raises(UpnpCommunicationError):
        await requester.async_http_request("GET", "http://192.168.1.1/desc.xml")
