# -*- coding: utf-8 -*-
"""Unit tests for event handler module."""

from datetime import timedelta
from typing import Generator, Sequence
from unittest.mock import Mock, patch

import pytest

from async_upnp_client.client import UpnpService, UpnpStateVariable
from async_upnp_client.client_factory import UpnpFactory
from async_upnp_client.const import HttpRequest
from async_upnp_client.event_handler import UpnpEventHandlerRegister

from .conftest import RESPONSE_MAP, UpnpTestNotifyServer, UpnpTestRequester


@pytest.fixture
def patched_local_ip() -> Generator:
    """Patch get_local_ip to `'192.168.1.2"`."""
    with patch("async_upnp_client.event_handler.get_local_ip") as mock:
        yield mock


@pytest.mark.asyncio
async def test_subscribe() -> None:
    """Test subscribing to a UpnpService."""
    requester = UpnpTestRequester(RESPONSE_MAP)
    factory = UpnpFactory(requester)
    device = await factory.async_create_device("http://dlna_dmr:1234/device.xml")
    notify_server = UpnpTestNotifyServer(
        requester=requester,
        source=("192.168.1.2", 8090),
    )
    event_handler = notify_server.event_handler

    service = device.service("urn:schemas-upnp-org:service:RenderingControl:1")
    sid, timeout = await event_handler.async_subscribe(service)
    assert event_handler.service_for_sid("uuid:dummy") == service
    assert sid == "uuid:dummy"
    assert timeout == timedelta(seconds=300)
    assert event_handler.callback_url == "http://192.168.1.2:8090/notify"


@pytest.mark.asyncio
async def test_subscribe_renew() -> None:
    """Test renewing an existing subscription to a UpnpService."""
    requester = UpnpTestRequester(RESPONSE_MAP)
    factory = UpnpFactory(requester)
    device = await factory.async_create_device("http://dlna_dmr:1234/device.xml")
    notify_server = UpnpTestNotifyServer(
        requester=requester,
        source=("192.168.1.2", 8090),
    )
    event_handler = notify_server.event_handler

    service = device.service("urn:schemas-upnp-org:service:RenderingControl:1")
    sid, timeout = await event_handler.async_subscribe(service)
    assert sid == "uuid:dummy"
    assert event_handler.service_for_sid("uuid:dummy") == service
    assert timeout == timedelta(seconds=300)

    sid, timeout = await event_handler.async_resubscribe(service)
    assert event_handler.service_for_sid("uuid:dummy") == service
    assert sid == "uuid:dummy"
    assert timeout == timedelta(seconds=300)


@pytest.mark.asyncio
async def test_unsubscribe() -> None:
    """Test unsubscribing from a UpnpService."""
    requester = UpnpTestRequester(RESPONSE_MAP)
    factory = UpnpFactory(requester)
    device = await factory.async_create_device("http://dlna_dmr:1234/device.xml")
    notify_server = UpnpTestNotifyServer(
        requester=requester,
        source=("192.168.1.2", 8090),
    )
    event_handler = notify_server.event_handler

    service = device.service("urn:schemas-upnp-org:service:RenderingControl:1")
    sid, timeout = await event_handler.async_subscribe(service)
    assert event_handler.service_for_sid("uuid:dummy") == service
    assert sid == "uuid:dummy"
    assert timeout == timedelta(seconds=300)

    old_sid = await event_handler.async_unsubscribe(service)
    assert event_handler.service_for_sid("uuid:dummy") is None
    assert old_sid == "uuid:dummy"


@pytest.mark.asyncio
async def test_on_notify_upnp_event() -> None:
    """Test handling of a UPnP event."""
    changed_vars: Sequence[UpnpStateVariable] = []

    def on_event(
        _self: UpnpService, changed_state_variables: Sequence[UpnpStateVariable]
    ) -> None:
        nonlocal changed_vars
        changed_vars = changed_state_variables

    requester = UpnpTestRequester(RESPONSE_MAP)
    notify_server = UpnpTestNotifyServer(
        requester=requester,
        source=("192.168.1.2", 8090),
    )
    event_handler = notify_server.event_handler
    factory = UpnpFactory(requester)
    device = await factory.async_create_device("http://dlna_dmr:1234/device.xml")
    service = device.service("urn:schemas-upnp-org:service:RenderingControl:1")
    service.on_event = on_event
    await event_handler.async_subscribe(service)

    headers = {
        "NT": "upnp:event",
        "NTS": "upnp:propchange",
        "SID": "uuid:dummy",
    }
    body = """
<e:propertyset xmlns:e="urn:schemas-upnp-org:event-1-0">
    <e:property>
        <Volume>60</Volume>
    </e:property>
</e:propertyset>
"""

    http_request = HttpRequest(
        "NOTIFY", "http://dlna_dmr:1234/upnp/event/RenderingControl1", headers, body
    )
    result = await event_handler.handle_notify(http_request)
    assert result == 200

    assert len(changed_vars) == 1

    state_var = service.state_variable("Volume")
    assert state_var.value == 60


@pytest.mark.asyncio
async def test_register_device(patched_local_ip: Mock) -> None:
    """Test registering a device with a UpnpEventHandlerRegister."""
    # pylint: disable=redefined-outer-name
    requester = UpnpTestRequester(RESPONSE_MAP)
    register = UpnpEventHandlerRegister(requester, UpnpTestNotifyServer)
    patched_local_ip.return_value = "192.168.1.2"

    factory = UpnpFactory(requester)
    device = await factory.async_create_device("http://dlna_dmr:1234/device.xml")

    event_handler = await register.async_add_device(device)
    assert event_handler is not None
    assert event_handler.callback_url == "http://192.168.1.2:0/notify"
    assert register.has_event_handler_for_device(device)


@pytest.mark.asyncio
async def test_register_device_different_source_address(patched_local_ip: Mock) -> None:
    """Test registering two devices with different source IPs with a UpnpEventHandlerRegister."""
    # pylint: disable=redefined-outer-name
    requester = UpnpTestRequester(RESPONSE_MAP)
    register = UpnpEventHandlerRegister(requester, UpnpTestNotifyServer)
    factory = UpnpFactory(requester)

    patched_local_ip.return_value = "192.168.1.2"
    device_1 = await factory.async_create_device("http://dlna_dmr:1234/device.xml")
    event_handler_1 = await register.async_add_device(device_1)
    assert event_handler_1 is not None
    assert event_handler_1.callback_url == "http://192.168.1.2:0/notify"

    patched_local_ip.return_value = "192.168.2.2"
    device_2 = await factory.async_create_device("http://igd:1234/device.xml")
    event_handler_2 = await register.async_add_device(device_2)
    assert event_handler_2 is not None
    assert event_handler_2.callback_url == "http://192.168.2.2:0/notify"


@pytest.mark.asyncio
async def test_remove_device(patched_local_ip: Mock) -> None:
    """Test removing a device from a UpnpEventHandlerRegister."""
    # pylint: disable=redefined-outer-name
    requester = UpnpTestRequester(RESPONSE_MAP)
    register = UpnpEventHandlerRegister(requester, UpnpTestNotifyServer)
    factory = UpnpFactory(requester)

    patched_local_ip.return_value = "192.168.1.2"
    device_1 = await factory.async_create_device("http://dlna_dmr:1234/device.xml")
    device_2 = await factory.async_create_device("http://igd:1234/device.xml")

    event_handler_1 = await register.async_add_device(device_1)
    event_handler_2 = await register.async_add_device(device_2)
    assert event_handler_1 is event_handler_2

    removed_event_handler_1 = await register.async_remove_device(device_1)
    assert removed_event_handler_1 is None  # UpnpEventHandler is still being used
    removed_event_handler_2 = await register.async_remove_device(device_2)
    assert removed_event_handler_2 is event_handler_1
