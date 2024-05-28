"""Test server functionality."""

import asyncio
import socket
import xml.etree.ElementTree as ET
from collections import namedtuple
from contextlib import asynccontextmanager, suppress
from typing import (
    Any,
    AsyncGenerator,
    AsyncIterator,
    Awaitable,
    Callable,
    Dict,
    Optional,
    Tuple,
)

import aiohttp
import pytest
import pytest_asyncio

import async_upnp_client.aiohttp
import async_upnp_client.client
import async_upnp_client.server
from async_upnp_client.client import UpnpStateVariable
from async_upnp_client.const import DeviceInfo, ServiceInfo
from async_upnp_client.server import (
    UpnpServer,
    UpnpServerDevice,
    UpnpServerService,
    callable_action,
    create_event_var,
    create_state_var,
)

from .conftest import read_file


class ServerServiceTest(UpnpServerService):
    """Test Service."""

    SERVICE_DEFINITION = ServiceInfo(
        service_id="urn:upnp-org:serviceId:TestServerService",
        service_type="urn:schemas-upnp-org:service:TestServerService:1",
        control_url="/upnp/control/TestServerService",
        event_sub_url="/upnp/event/TestServerService",
        scpd_url="/ContentDirectory.xml",
        xml=ET.Element("server_service"),
    )

    STATE_VARIABLE_DEFINITIONS = {
        "TestVariable_str": create_state_var("string"),
        "EventableTextVariable_ui4": create_event_var("ui4", default="0"),
        "A_ARG_TYPE_In_Var1_str": create_state_var("string"),
        "A_ARG_TYPE_In_Var2_ui4": create_state_var("ui4"),
    }

    @callable_action(
        name="SetValues",
        in_args={
            "In_Var1_str": "A_ARG_TYPE_In_Var1_str",
        },
        out_args={
            "TestVariable_str": "TestVariable_str",
            "EventableTextVariable_ui4": "EventableTextVariable_ui4",
        },
    )
    async def set_values(
        self, In_Var1_str: str  # pylint: disable=invalid-name
    ) -> Dict[str, UpnpStateVariable]:
        """Handle action."""
        self.state_variable("TestVariable_str").value = In_Var1_str
        return {
            "TestVariable_str": self.state_variable("TestVariable_str"),
            "EventableTextVariable_ui4": self.state_variable(
                "EventableTextVariable_ui4"
            ),
        }

    def set_eventable(self, value: int) -> None:
        """Eventable state-variable assignment."""
        event_var = self.state_variable("EventableTextVariable_ui4")
        event_var.value = value


class ServerDeviceTest(UpnpServerDevice):
    """Test device."""

    DEVICE_DEFINITION = DeviceInfo(
        device_type=":urn:schemas-upnp-org:device:TestServerDevice:1",
        friendly_name="Test Server",
        manufacturer="Test",
        manufacturer_url=None,
        model_name="TestServer",
        model_url=None,
        udn="uuid:adca2e25-cbe4-427a-a5c3-9b5931e7b79b",
        upc=None,
        model_description="Test Server",
        model_number="v0.0.1",
        serial_number="0000001",
        presentation_url=None,
        url="/device.xml",
        icons=[],
        xml=ET.Element("server_device"),
    )
    EMBEDDED_DEVICES = []
    SERVICES = [ServerServiceTest]


class AppRunnerMock:
    """Mock AppRunner."""

    # pylint: disable=too-few-public-methods

    def __init__(self, app: Any, *_args: Any, **_kwargs: Any) -> None:
        """Initialize."""
        self.app = app

    async def setup(self) -> None:
        """Configure AppRunner."""


class MockSocket:
    """Mock socket without 'bind'."""

    def __init__(self, sock: socket.socket) -> None:
        """Initialize."""
        self.sock = sock

    def bind(self, addr: Any) -> None:
        """Ignore bind."""

    def __getattr__(self, name: str) -> Any:
        """Passthrough."""
        return getattr(self.sock, name)


class Callback:
    """HTTP server to process callbacks."""

    def __init__(self) -> None:
        """Initialize."""
        self.callback: Optional[
            Callable[[aiohttp.web.Request], Awaitable[aiohttp.web.Response]]
        ] = None
        self.session = None
        self.app = aiohttp.web.Application()
        self.app.router.add_route("NOTIFY", "/{tail:.*}", self.handler)

    async def start(self, aiohttp_client: Any) -> None:
        """Generate session."""
        self.session = await aiohttp_client(self.app)

    def set_callback(
        self, callback: Callable[[aiohttp.web.Request], Awaitable[aiohttp.web.Response]]
    ) -> None:
        """Assign callback."""
        self.callback = callback

    async def handler(self, request: aiohttp.web.Request) -> aiohttp.web.Response:
        """Handle callback."""
        if self.callback:
            return await self.callback(request)  # pylint: disable=not-callable
        return aiohttp.web.Response(status=200)

    @asynccontextmanager
    async def ClientSession(self) -> AsyncIterator:  # pylint: disable=invalid-name
        """Test session."""
        if self.session:
            yield self.session


@pytest_asyncio.fixture
async def upnp_server(monkeypatch: Any, aiohttp_client: Any) -> AsyncGenerator:
    """Fixture to initialize device."""
    # pylint: disable=too-few-public-methods

    ssdp_sockets = []
    http_client = None

    def get_ssdp_socket_mock(
        *_args: Any, **_kwargs: Any
    ) -> Tuple[MockSocket, None, None]:
        sock1, sock2 = socket.socketpair(socket.AF_UNIX, socket.SOCK_DGRAM)
        ssdp_sockets.append(sock2)
        return MockSocket(sock1), None, None

    class TCPSiteMock:
        """Mock TCP connection."""

        def __init__(
            self, runner: aiohttp.web.AppRunner, *_args: Any, **_kwargs: Any
        ) -> None:
            self.app = runner.app
            self.name = "TCPSiteMock"

        async def start(self) -> Any:
            """Create HTTP server."""
            nonlocal http_client
            http_client = await aiohttp_client(self.app)
            return http_client

    callback = Callback()
    monkeypatch.setattr(async_upnp_client.server, "AppRunner", AppRunnerMock)
    monkeypatch.setattr(async_upnp_client.server, "TCPSite", TCPSiteMock)
    monkeypatch.setattr(
        async_upnp_client.server, "get_ssdp_socket", get_ssdp_socket_mock
    )
    monkeypatch.setattr(
        async_upnp_client.aiohttp, "ClientSession", callback.ClientSession
    )
    server = UpnpServer(
        ServerDeviceTest, ("127.0.0.1", 0), http_port=80, boot_id=1, config_id=1
    )
    await server.async_start()

    await callback.start(aiohttp_client)
    upnpserver = namedtuple("upnpserver", "http_client ssdp_sockets callback server")
    yield upnpserver(http_client, ssdp_sockets, callback, server)
    # await server.async_stop()
    for sock in ssdp_sockets:
        sock.close()


@pytest.mark.asyncio
async def test_init(upnp_server: Any) -> None:
    """Test device query."""
    # pylint: disable=redefined-outer-name
    http_client = upnp_server.http_client
    response = await http_client.get("/device.xml")
    assert response.status == 200
    data = await response.text()
    assert data == read_file("server/device.xml").strip()


@pytest.mark.asyncio
async def test_action(upnp_server: Any) -> None:
    """Test action execution."""
    # pylint: disable=redefined-outer-name
    http_client = upnp_server.http_client
    response = await http_client.post(
        "/upnp/control/TestServerService",
        data=read_file("server/action_request.xml"),
        headers={
            "content-type": 'text/xml; charset="utf-8"',
            "user-agent": "Linux/1.0 UPnP/1.1 test/1.0",
            "soapaction": "urn:schemas-upnp-org:service:TestServerService:1#SetValues",
        },
    )
    assert response.status == 200
    data = await response.text()
    assert data == read_file("server/action_response.xml").strip()


@pytest.mark.asyncio
async def test_subscribe(upnp_server: Any) -> None:
    """Test subscription to server event."""
    # pylint: disable=redefined-outer-name
    event = asyncio.Event()
    expect = 0

    async def on_callback(request: aiohttp.web.Request) -> aiohttp.web.Response:
        nonlocal expect
        data = await request.read()
        assert (
            data
            == read_file(f"server/subscribe_response_{expect}.xml").strip().encode()
        )
        expect += 1
        event.set()
        return aiohttp.web.Response(status=200)

    http_client = upnp_server.http_client
    callback = upnp_server.callback
    service: ServerServiceTest = (
        upnp_server.server._device.service(  # pylint: disable=protected-access
            "urn:schemas-upnp-org:service:TestServerService:1"
        )
    )
    callback.set_callback(on_callback)
    response = await http_client.request(
        "SUBSCRIBE",
        "/upnp/event/TestServerService",
        headers={"CALLBACK": "</foo/bar>", "NT": "upnp:event", "TIMEOUT": "Second-30"},
    )
    assert response.status == 200
    data = await response.text()
    assert not data
    sid = response.headers.get("SID")
    assert sid
    with suppress(asyncio.TimeoutError):
        await asyncio.wait_for(event.wait(), 2)
    assert event.is_set()

    event.clear()
    while not service.get_subscriber(sid):
        await asyncio.sleep(0)
    service.set_eventable(1)
    with suppress(asyncio.TimeoutError):
        await asyncio.wait_for(event.wait(), 2)
    assert event.is_set()
