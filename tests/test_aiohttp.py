"""Unit tests for aiohttp."""
# pylint: disable=protected-access

from unittest.mock import MagicMock, patch

import pytest

from async_upnp_client.aiohttp import AiohttpNotifyServer, AiohttpRequester
from async_upnp_client.exceptions import UpnpCommunicationError

from .conftest import RESPONSE_MAP, UpnpTestRequester


def test_server_init() -> None:
    """Test initialization of an AiohttpNotifyServer."""
    requester = UpnpTestRequester(RESPONSE_MAP)
    server = AiohttpNotifyServer(requester, ("192.168.1.2", 8090))
    assert server._loop is not None
    assert server.listen_host == "192.168.1.2"
    assert server.listen_port == 8090
    assert server.callback_url == "http://192.168.1.2:8090/notify"
    assert server.event_handler is not None

    server = AiohttpNotifyServer(
        requester, ("192.168.1.2", 8090), "http://1.2.3.4:8091/"
    )
    assert server.callback_url == "http://1.2.3.4:8091/"


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
