"""Unit tests for aiohttp."""

import pytest

from async_upnp_client.aiohttp import AiohttpNotifyServer
from async_upnp_client.utils import async_get_local_ip

from .upnp_test_requester import RESPONSE_MAP, UpnpTestRequester


class TestAiohttpNotifyServer:
    """Tests for AiohttpNotifyServer."""

    def test_init(self):
        """Test initialization of an AiohttpNotifyServer."""
        requester = UpnpTestRequester(RESPONSE_MAP)
        server = AiohttpNotifyServer(requester)
        assert server._loop is not None
        assert server._listen_host is None
        assert server._listen_port == 0
        with pytest.raises(ValueError, match=r"callback_url format.* port"):
            server.callback_url
        assert server._aiohttp_server is None
        assert server._server is None
        assert server.event_handler is not None

        server = AiohttpNotifyServer(requester, 80, "localhost")
        assert server._listen_host == "localhost"
        assert server._listen_port == 80
        assert server.callback_url == "http://localhost:80/notify"

        server = AiohttpNotifyServer(requester, 80, "localhost", "http://1.2.3.4:88")
        assert server.callback_url == "http://1.2.3.4:88"

    @pytest.mark.asyncio
    async def test_start_server(self):
        """Test start_server creates internal servers on appropriate addresses."""
        requester = UpnpTestRequester(RESPONSE_MAP)
        server = AiohttpNotifyServer(requester)
        assert server.event_handler.listen_ports == {}
        await server.start_server()
        assert server._aiohttp_server is not None
        assert server._server is not None
        assert len(server.event_handler.listen_ports) >= 1
        addr_family, host = await async_get_local_ip()
        port = server.event_handler.listen_ports[addr_family]
        expect_callback_url = "http://{host}:{port}/notify".format(host=host, port=port)
        assert server.callback_url == expect_callback_url

    @pytest.mark.asyncio
    async def test_stop_server(self):
        """Test stop_server deletes internal servers."""
        requester = UpnpTestRequester(RESPONSE_MAP)
        server = AiohttpNotifyServer(requester)
        await server.start_server()
        await server.stop_server()
        assert server.event_handler is not None
        assert server.event_handler.listen_ports == {}
        assert server._aiohttp_server is None
        assert server._server is None
