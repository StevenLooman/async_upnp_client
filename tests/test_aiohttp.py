"""Unit tests for aiohttp."""

# pylint: disable=protected-access

import asyncio
from typing import Any
from unittest.mock import MagicMock, patch

import aiohttp
import pytest
from aiohttp import web

from async_upnp_client.aiohttp import (
    AiohttpNotifyServer,
    AiohttpRequester,
    AiohttpSessionRequester,
    _fixed_host_header,
)
from async_upnp_client.const import HttpRequest
from async_upnp_client.exceptions import UpnpCommunicationError, UpnpConnectionTimeoutError

from .conftest import RESPONSE_MAP, UpnpTestRequester


def test_fixed_host_header() -> None:
    """Test _fixed_host_header."""
    # pylint: disable=C1803
    assert _fixed_host_header("http://192.168.1.1:8000/desc") == {}
    assert _fixed_host_header("http://router.local:8000/desc") == {}
    assert _fixed_host_header("http://[fe80::1%10]:8000/desc") == {"Host": "[fe80::1]:8000"}

    assert _fixed_host_header("http://192.168.1.1/desc") == {}
    assert _fixed_host_header("http://router.local/desc") == {}
    assert _fixed_host_header("http://[fe80::1%10]/desc") == {"Host": "[fe80::1]"}

    assert _fixed_host_header("https://192.168.1.1/desc") == {}
    assert _fixed_host_header("https://router.local/desc") == {}
    assert _fixed_host_header("https://[fe80::1%10]/desc") == {"Host": "[fe80::1]"}

    assert _fixed_host_header("http://192.168.1.1:8000/root%desc") == {}
    assert _fixed_host_header("http://router.local:8000/root%desc") == {}
    assert _fixed_host_header("http://[fe80::1]:8000/root%desc") == {}


@pytest.mark.asyncio
async def test_server_init() -> None:
    """Test initialization of an AiohttpNotifyServer."""
    requester = UpnpTestRequester(RESPONSE_MAP)
    server = AiohttpNotifyServer(requester, ("192.168.1.2", 8090))
    assert server._loop is not None
    assert server.listen_host == "192.168.1.2"
    assert server.listen_port == 8090
    assert server.callback_url == "http://192.168.1.2:8090/notify"
    assert server.event_handler is not None

    server = AiohttpNotifyServer(requester, ("192.168.1.2", 8090), "http://1.2.3.4:8091/")
    assert server.callback_url == "http://1.2.3.4:8091/"


@pytest.mark.asyncio
@patch(
    "async_upnp_client.aiohttp.aiohttp.ClientSession.request",
    side_effect=UnicodeDecodeError("", b"", 0, 1, ""),
)
async def test_client_decode_error(_mock_request: MagicMock) -> None:
    """Test handling unicode decode error."""
    requester = AiohttpRequester()
    request = HttpRequest("GET", "http://192.168.1.1/desc.xml", {}, None)
    with pytest.raises(UpnpCommunicationError):
        await requester.async_http_request(request)


async def _slow_handler(_request: web.Request) -> web.Response:
    """Answer only after 0.5 s, like a renderer holding back its Play response."""
    await asyncio.sleep(0.5)
    return web.Response(text="ok")


@pytest.mark.parametrize("requester_class", [AiohttpRequester, AiohttpSessionRequester])
async def test_request_timeout_overrides_default(aiohttp_server: Any, requester_class: type) -> None:
    """A per-request timeout overrides the requester default timeout."""
    app = web.Application()
    app.router.add_post("/control", _slow_handler)
    server = await aiohttp_server(app)
    url = str(server.make_url("/control"))

    async with aiohttp.ClientSession() as session:
        requester: AiohttpRequester | AiohttpSessionRequester
        if requester_class is AiohttpSessionRequester:
            requester = AiohttpSessionRequester(session, timeout=0.2)  # type: ignore[arg-type]
        else:
            requester = AiohttpRequester(timeout=0.2)  # type: ignore[arg-type]

        # requester default (0.2 s) is too short for the slow response
        with pytest.raises(UpnpConnectionTimeoutError):
            await requester.async_http_request(HttpRequest("POST", url, {}, None))

        # a longer per-request timeout succeeds
        response = await requester.async_http_request(HttpRequest("POST", url, {}, None, timeout=2.0))
        assert response.status_code == 200
        assert response.body == "ok"


def test_timeout_for() -> None:
    """The per-request timeout is used when set, else the requester default."""
    requester = AiohttpRequester(timeout=5)
    assert requester._timeout_for(HttpRequest("GET", "http://x/", {}, None)).total == 5.0
    assert requester._timeout_for(HttpRequest("GET", "http://x/", {}, None, timeout=30)).total == 30.0


async def test_session_requester_does_not_retry_timeout(aiohttp_server: Any) -> None:
    """A timed-out request is not re-sent (the device may still be processing it)."""
    calls = 0

    async def handler(_request: web.Request) -> web.Response:
        nonlocal calls
        calls += 1
        await asyncio.sleep(0.5)
        return web.Response(text="ok")

    app = web.Application()
    app.router.add_post("/control", handler)
    server = await aiohttp_server(app)
    async with aiohttp.ClientSession() as session:
        requester = AiohttpSessionRequester(session, timeout=0.2)  # type: ignore[arg-type]
        with pytest.raises(UpnpConnectionTimeoutError):
            await requester.async_http_request(HttpRequest("POST", str(server.make_url("/control")), {}, None))
    await asyncio.sleep(0.6)  # let the server finish the request it received
    assert calls == 1
