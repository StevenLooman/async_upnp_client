import os
from copy import copy
from typing import Mapping, Tuple

import pytest
from multidict import CIMultiDict

from async_upnp_client.client_factory import UpnpFactory
from async_upnp_client.const import HttpRequest, HttpResponse
from async_upnp_client.exceptions import UpnpActionResponseError
from async_upnp_client.profiles.ohmedia import (
    OhmDevice,
    _action_for_state_var,
    _decode_id_array,
    _list_to_string,
    _strict_false,
)

from ..conftest import UpnpTestNotifyServer, UpnpTestRequester


def read_file(filename: str) -> str:
    """Read file."""
    path = os.path.join("tests", "fixtures", "ohmedia", filename)
    with open(path, encoding="utf-8") as file:
        return file.read()


NOTIFY_PROPERTY_BODY = """
<e:propertyset xmlns:e="urn:schemas-upnp-org:event-1-0">
    <e:property>
        {prop_value}
    </e:property>
</e:propertyset>
"""

NOTIFY_HEADERS: CIMultiDict = CIMultiDict([("Nt", "upnp:event"), ("Nts", "upnp:propchange"), ("SID", "dummy-sid")])

RESPONSE_MAP: Mapping[Tuple[str, str], HttpResponse] = {
    # OpenHomeMedia
    ("GET", "http://ohmedia:1234/device.xml"): HttpResponse(
        200,
        {},
        read_file("device.xml"),
    ),
    (
        "GET",
        "http://ohmedia:1234/dummy_device_udn/Upnp/av.openhome.org-ConfigApp-1/service.xml",
    ): HttpResponse(
        200,
        {},
        read_file("Config1.xml"),
    ),
    (
        "GET",
        "http://ohmedia:1234/dummy_device_udn/Upnp/av.openhome.org-Product-4/service.xml",
    ): HttpResponse(
        200,
        {},
        read_file("Product4.xml"),
    ),
    (
        "GET",
        "http://ohmedia:1234/dummy_device_udn/Upnp/av.openhome.org-Volume-4/service.xml",
    ): HttpResponse(
        200,
        {},
        read_file("Volume4.xml"),
    ),
    (
        "GET",
        "http://ohmedia:1234/dummy_device_udn/Upnp/av.openhome.org-Playlist-1/service.xml",
    ): HttpResponse(
        200,
        {},
        read_file("Playlist1.xml"),
    ),
    (
        "SUBSCRIBE",
        "http://ohmedia:1234/dummy_device_udn/av.openhome.org-Volume-4/event",
    ): HttpResponse(
        200,
        {"sid": "uuid:dummy-volume-4", "timeout": "Second-300"},
        "",
    ),
    (
        "SUBSCRIBE",
        "http://ohmedia:1234/dummy_device_udn/av.openhome.org-Product-4/event",
    ): HttpResponse(
        200,
        {"sid": "uuid:dummy-product-4", "timeout": "Second-300"},
        "",
    ),
    (
        "SUBSCRIBE",
        "http://ohmedia:1234/dummy_device_udn/av.openhome.org-Playlist-1/event",
    ): HttpResponse(
        200,
        {"sid": "uuid:dummy-playlist-1", "timeout": "Second-300"},
        "",
    ),
    (
        "UNSUBSCRIBE",
        "http://ohmedia:1234/dummy_device_udn/av.openhome.org-Volume-4/event",
    ): HttpResponse(
        200,
        {"sid": "uuid:dummy-volume-4"},
        "",
    ),
    (
        "UNSUBSCRIBE",
        "http://ohmedia:1234/dummy_device_udn/av.openhome.org-Product-4/event",
    ): HttpResponse(
        200,
        {"sid": "uuid:dummy-product-4"},
        "",
    ),
    (
        "UNSUBSCRIBE",
        "http://ohmedia:1234/dummy_device_udn/av.openhome.org-Playlist-1/event",
    ): HttpResponse(
        200,
        {"sid": "uuid:dummy-playlist-1"},
        "",
    ),
}


# region profile tests
@pytest.mark.asyncio
async def test_instantiate_ohmdevice_no_handler() -> None:
    """Test async_wait_for_can_play times out waiting for ability to play."""
    requester = UpnpTestRequester(RESPONSE_MAP)
    factory = UpnpFactory(requester)
    device = await factory.async_create_device("http://ohmedia:1234/device.xml")
    profile = OhmDevice(device, event_handler=None)
    assert profile


@pytest.mark.asyncio
async def test_async_call_action_no_params() -> None:
    """Test _async_call_action with no kwargs"""
    requester = UpnpTestRequester(RESPONSE_MAP)
    factory = UpnpFactory(requester)
    device = await factory.async_create_device("http://ohmedia:1234/device.xml")
    profile = OhmDevice(device, event_handler=None)

    requester.response_map[
        (
            "POST",
            "http://ohmedia:1234/dummy_device_udn/av.openhome.org-Volume-4/control",
        )
    ] = HttpResponse(
        200,
        {},
        read_file("response_Volume_Volume.xml"),
    )

    assert (await profile._async_call_action("Volume", "Volume")) == {"Value": 42}


@pytest.mark.asyncio
async def test_async_call_action_one_param() -> None:
    """Test _async_call_action with one kwarg"""
    # following the zero, one, many principle

    requester = UpnpTestRequester(RESPONSE_MAP)
    factory = UpnpFactory(requester)
    device = await factory.async_create_device("http://ohmedia:1234/device.xml")
    profile = OhmDevice(device, event_handler=None)

    requester.response_map[
        (
            "POST",
            "http://ohmedia:1234/dummy_device_udn/av.openhome.org-Playlist-1/control",
        )
    ] = HttpResponse(
        200,
        {},
        read_file("response_Playlist_IdArrayChanged.xml"),
    )

    # playlist_id_array_changed
    assert (await profile._async_call_action("Playlist", "IdArrayChanged", Token=42)) == {"Value": True}


@pytest.mark.asyncio
async def test_async_call_action_many_params() -> None:
    """Test _async_call_action with several kwargs"""
    requester = UpnpTestRequester(RESPONSE_MAP)
    factory = UpnpFactory(requester)
    device = await factory.async_create_device("http://ohmedia:1234/device.xml")
    profile = OhmDevice(device, event_handler=None)

    requester.response_map[
        (
            "POST",
            "http://ohmedia:1234/dummy_device_udn/av.openhome.org-Playlist-1/control",
        )
    ] = HttpResponse(
        200,
        {},
        read_file("response_Playlist_Insert.xml"),
    )

    afterid = 123
    uri = "uri_for_track"
    metadata = "didl-lite_metadata"
    actual = await profile.playlist_insert(afterid, uri, metadata)
    assert actual == {"NewId": 50}


@pytest.mark.asyncio
async def test_state_var_value_from_state_var() -> None:
    # got from cache
    """Test _async_call_action with several kwargs"""
    requester = UpnpTestRequester(RESPONSE_MAP)
    factory = UpnpFactory(requester)
    device = await factory.async_create_device("http://ohmedia:1234/device.xml")
    profile = OhmDevice(device, event_handler=None)

    state_var = profile._state_variable("Volume", "Volume")
    assert state_var.value is None

    state_var.value = 49
    actual = await profile._state_var_value("Volume", "Volume")
    assert actual == 49


# endregion


@pytest.mark.asyncio
async def test_state_var_value_from_polled() -> None:
    # got from cache
    """Test _state_variable with call to device"""
    requester = UpnpTestRequester(RESPONSE_MAP)
    factory = UpnpFactory(requester)
    device = await factory.async_create_device("http://ohmedia:1234/device.xml")
    profile = OhmDevice(device, event_handler=None)

    requester.response_map[
        (
            "POST",
            "http://ohmedia:1234/dummy_device_udn/av.openhome.org-Volume-4/control",
        )
    ] = HttpResponse(
        200,
        {},
        read_file("response_Volume_Volume.xml"),
    )

    state_var = profile._state_variable("Volume", "Volume")
    assert state_var.value is None

    actual = await profile._state_var_value("Volume", "Volume")
    assert actual == 42


@pytest.mark.asyncio
async def test_subscribe_no_event_handler() -> None:
    """Test no event handler."""
    requester = UpnpTestRequester(RESPONSE_MAP)
    factory = UpnpFactory(requester)
    device = await factory.async_create_device("http://ohmedia:1234/device.xml")
    profile = OhmDevice(device, event_handler=None)
    # Doesn't error, but also doesn't do anything.
    timeout = await profile.async_subscribe_services()
    assert timeout is None


@pytest.mark.asyncio
async def test_async_call_action_bad_service() -> None:
    """Test _async_call_action with non-existent service"""
    requester = UpnpTestRequester(RESPONSE_MAP)
    factory = UpnpFactory(requester)
    device = await factory.async_create_device("http://ohmedia:1234/device.xml")
    profile = OhmDevice(device, event_handler=None)
    # doesn't do anything but doesn't error
    await profile._async_call_action("NoService", "Action")


@pytest.mark.asyncio
async def test_async_call_action_bad_action() -> None:
    """Test _async_call_action with non-existent action for service"""
    requester = UpnpTestRequester(RESPONSE_MAP)
    factory = UpnpFactory(requester)
    device = await factory.async_create_device("http://ohmedia:1234/device.xml")
    profile = OhmDevice(device, event_handler=None)
    # doesn't do anything but doesn't error
    await profile._async_call_action("Volume", "Action")


@pytest.mark.asyncio
async def test_async_call_action_bad_param_value() -> None:
    """Test _async_call_action with no kwargs"""
    with pytest.raises(UpnpActionResponseError) as exinfo:  # call action expecting 800 upnp error
        requester = UpnpTestRequester(RESPONSE_MAP)
        factory = UpnpFactory(requester)
        device = await factory.async_create_device("http://ohmedia:1234/device.xml")
        profile = OhmDevice(device, event_handler=None)

        requester.response_map[
            (
                "POST",
                "http://ohmedia:1234/dummy_device_udn/av.openhome.org-Playlist-1/control",
            )
        ] = HttpResponse(
            500,
            {},
            read_file("error_Playlist_DeleteId_Id_Not_Found.xml"),
        )

        await profile._async_call_action("Playlist", "DeleteId", Value=1)
    assert "upnp error: 800" in str(exinfo.value)


@pytest.mark.asyncio
async def test_subscribe_events() -> None:
    """Test that profile can subscribe to service events."""

    requester = UpnpTestRequester(RESPONSE_MAP)
    factory = UpnpFactory(requester)
    device = await factory.async_create_device("http://ohmedia:1234/device.xml")

    notify_server = UpnpTestNotifyServer(
        requester=requester,
        source=("192.168.1.2", 8090),
    )
    event_handler = notify_server.event_handler

    profile = OhmDevice(device, event_handler=event_handler)
    timeout = await profile.async_subscribe_services()
    assert timeout is not None

    headers = copy(NOTIFY_HEADERS)  # hey teacher, leave them constants alone
    headers["SID"] = "uuid:dummy-volume-4"
    expected = 49
    body = NOTIFY_PROPERTY_BODY.format(prop_value=f"<Volume>{expected}</Volume>")
    http_request = HttpRequest(
        method="NOTIFY",
        url="http://192.168.1.2:8090/notify",
        headers=headers,
        body=body,
    )
    result = await event_handler.handle_notify(http_request)
    assert result == 200

    state_var = profile._state_variable(service_name="Volume", state_variable_name="Volume")
    assert state_var.value == expected


# endregion


# region tests of functions not requiring a profile
def test_action_for_state_var_mapped() -> None:
    # what action needs to be called to populate specified state variable
    actual = _action_for_state_var("Info", "TrackCount")
    assert actual == "Counters"


def test_action_for_state_var_not_mapped() -> None:
    # action has same name as specified state variable
    actual = _action_for_state_var("Playlist", "TransportState")
    assert actual == "TransportState"


def test_decode_id_array() -> None:
    data = "AAAAEwAAABQAAAAVAAAAFgAAABcAAAAdAAAAHgAAAB8="
    assert _decode_id_array(data) == [19, 20, 21, 22, 23, 29, 30, 31]


def test_decode_id_array_empty() -> None:
    data = ""
    assert _decode_id_array(data) == []


def test_decode_id_array_not_an_array() -> None:
    data = b"Tm90IEFuIEFycmF5"
    assert _decode_id_array(data) == []


def test_list_to_string() -> None:
    idlist = [1, 2, 3, 4, 5]
    assert _list_to_string(idlist) == "1 2 3 4 5"
    idlist = []
    assert _list_to_string(idlist) == ""


def test_strict_false() -> None:
    assert _strict_false(False) == False
    assert _strict_false("False") == False
    assert _strict_false(0) == False
    assert _strict_false("any string (other than False)") == True
    assert _strict_false("false") == True
    assert _strict_false("true") == True
    assert _strict_false(True) == True
    assert _strict_false(1) == True
    assert _strict_false([]) == True
    assert _strict_false({}) == True
    assert _strict_false("") == True
    assert _strict_false(None) == True
    assert _strict_false(set()) == True


# endregion
