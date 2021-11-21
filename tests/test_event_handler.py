# -*- coding: utf-8 -*-
"""Tests for UPnpEventHandler."""

from datetime import timedelta
from typing import Sequence

import pytest

from async_upnp_client import (
    UpnpEventHandler,
    UpnpFactory,
    UpnpService,
    UpnpStateVariable,
)

from .conftest import RESPONSE_MAP, UpnpTestNotifyServer, UpnpTestRequester


@pytest.mark.asyncio
async def test_subscribe() -> None:
    """Test subscribing to a UpnpService."""
    notify_server = UpnpTestNotifyServer()
    requester = UpnpTestRequester(RESPONSE_MAP)
    factory = UpnpFactory(requester)
    device = await factory.async_create_device("http://dlna_dmr:1234/device.xml")
    event_handler = UpnpEventHandler(notify_server, requester)

    service = device.service("urn:schemas-upnp-org:service:RenderingControl:1")
    sid, timeout = await event_handler.async_subscribe(service)
    assert event_handler.service_for_sid("uuid:dummy") == service
    assert sid == "uuid:dummy"
    assert timeout == timedelta(seconds=300)


@pytest.mark.asyncio
async def test_subscribe_renew() -> None:
    """Test renewing an existing subscription to a UpnpService."""
    notify_server = UpnpTestNotifyServer()
    requester = UpnpTestRequester(RESPONSE_MAP)
    factory = UpnpFactory(requester)
    device = await factory.async_create_device("http://dlna_dmr:1234/device.xml")
    event_handler = UpnpEventHandler(notify_server, requester)

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
    notify_server = UpnpTestNotifyServer()
    requester = UpnpTestRequester(RESPONSE_MAP)
    factory = UpnpFactory(requester)
    device = await factory.async_create_device("http://dlna_dmr:1234/device.xml")
    event_handler = UpnpEventHandler(notify_server, requester)

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

    notify_server = UpnpTestNotifyServer()
    requester = UpnpTestRequester(RESPONSE_MAP)
    factory = UpnpFactory(requester)
    event_handler = UpnpEventHandler(notify_server, requester)
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

    result = await event_handler.handle_notify(headers, body)
    assert result == 200

    assert len(changed_vars) == 1

    state_var = service.state_variable("Volume")
    assert state_var.value == 60
