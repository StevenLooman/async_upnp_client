"""Unit tests for the Linn/Open Home Media profile."""

# pylint: disable=protected-access,line-too-long

import os
from copy import copy
from typing import Mapping, Tuple

import pytest
from multidict import CIMultiDict

from async_upnp_client.client_factory import UpnpFactory
from async_upnp_client.const import HttpRequest, HttpResponse
from async_upnp_client.exceptions import UpnpActionResponseError, UpnpError
from async_upnp_client.profiles.ohmedia import OhmDevice, _decode_id_array, _list_to_string

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
    ("GET", "http://ohmedia:1234/device_no_volume.xml"): HttpResponse(
        200,
        {},
        read_file("device_no_volume.xml"),
    ),
    ("GET", "http://ohmedia:1234/device_no_standby.xml"): HttpResponse(
        200,
        {},
        read_file("device_no_standby.xml"),
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
        "http://ohmedia:1234/dummy_device_udn/Upnp/av.openhome.org-Product-4/Product4_no_standby.xml",
    ): HttpResponse(
        200,
        {},
        read_file("Product4_no_standby.xml"),
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
    """Test _async_call_action with no kwargs."""
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
    """Test _async_call_action with one kwarg."""
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
    """Test _async_call_action with several kwargs."""
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
    actual = await profile.async_playlist_insert(afterid, uri, metadata)
    assert actual == {"NewId": 50}


@pytest.mark.asyncio
async def test_state_var_value_from_state_var() -> None:
    # get from cache
    """Test _async_call_action with several kwargs."""
    requester = UpnpTestRequester(RESPONSE_MAP)
    factory = UpnpFactory(requester)
    device = await factory.async_create_device("http://ohmedia:1234/device.xml")
    profile = OhmDevice(device, event_handler=None)

    state_var = profile._state_variable("Volume", "Volume")
    assert state_var is not None
    assert state_var.value is None

    state_var.value = 49
    actual = profile.get_state_variable_value("Volume", "Volume")
    assert actual is not None
    assert actual == 49


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
    """Test _async_call_action with non-existent service."""
    requester = UpnpTestRequester(RESPONSE_MAP)
    factory = UpnpFactory(requester)
    device = await factory.async_create_device("http://ohmedia:1234/device.xml")
    profile = OhmDevice(device, event_handler=None)
    # raises AttributeError
    with pytest.raises(UpnpError):
        await profile._async_call_action("NoService", "Action")


@pytest.mark.asyncio
async def test_async_call_action_bad_action() -> None:
    """Test _async_call_action with non-existent action for service."""
    requester = UpnpTestRequester(RESPONSE_MAP)
    factory = UpnpFactory(requester)
    device = await factory.async_create_device("http://ohmedia:1234/device.xml")
    profile = OhmDevice(device, event_handler=None)
    # raises KeyError
    with pytest.raises(UpnpError):
        await profile._async_call_action("Volume", "Action")


@pytest.mark.asyncio
async def test_async_call_action_bad_param_value() -> None:
    """Test _async_call_action with no kwargs."""
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

    headers = copy(NOTIFY_HEADERS)
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
    assert state_var is not None
    assert state_var.value == expected


@pytest.mark.asyncio
async def test_sources_valid_input() -> None:
    """Test sources with valid input returns correct value."""

    requester = UpnpTestRequester(RESPONSE_MAP)
    factory = UpnpFactory(requester)
    device = await factory.async_create_device("http://ohmedia:1234/device.xml")
    profile = OhmDevice(device, event_handler=None)

    requester.response_map[
        (
            "POST",
            "http://ohmedia:1234/dummy_device_udn/av.openhome.org-Product-4/control",
        )
    ] = HttpResponse(
        200,
        {},
        read_file("response_Product_SourceXml_valid.xml"),
    )

    expected = "{'Value': '<SourceList><Source><Name>Playlist</Name><Type>Playlist</Type><Visible>true</Visible><SystemName>Playlist</SystemName></Source><Source><Name>Radio</Name><Type>Radio</Type><Visible>true</Visible><SystemName>Radio</SystemName></Source><Source><Name>UPnP</Name><Type>UpnpAv</Type><Visible>false</Visible><SystemName>UPnP AV</SystemName></Source></SourceList>'}"
    actual = await profile._async_call_action("Product", "SourceXml")
    # actual = await profile.async_sources("Product", "SourceXml")
    assert str(actual) == expected


@pytest.mark.asyncio
async def test_has_product_standby() -> None:
    """Test has_product_standby returns True when service Product and action Standby are present."""

    requester = UpnpTestRequester(RESPONSE_MAP)
    factory = UpnpFactory(requester)
    device = await factory.async_create_device("http://ohmedia:1234/device.xml")
    profile = OhmDevice(device, event_handler=None)
    assert profile.has_product_standby


@pytest.mark.asyncio
async def test_has_volume_when_service_not_present() -> None:
    """Test has_volume returns False when Volume service is not present.

    device_no_volume.xml modified so that no Volume service is advertised
    """

    requester = UpnpTestRequester(RESPONSE_MAP)
    factory = UpnpFactory(requester)
    device = await factory.async_create_device("http://ohmedia:1234/device_no_volume.xml")
    profile = OhmDevice(device, event_handler=None)

    assert not profile.has_volume


@pytest.mark.asyncio
async def test_has_product_standby_when_action_not_present() -> None:
    """Test has_product_standby returns False when action is not present.

    device_no_standby.xml fixture modified to use Product4_no_standby.xml for Product4 service.xml
    Product4_no_standby.xml fixture modified so that Standby action is not present
    """

    requester = UpnpTestRequester(RESPONSE_MAP)
    factory = UpnpFactory(requester)
    device = await factory.async_create_device("http://ohmedia:1234/device_no_standby.xml")
    profile = OhmDevice(device, event_handler=None)

    assert not profile.has_product_standby


@pytest.mark.asyncio
async def test_has_source_type() -> None:
    """Test has_source_type."""

    requester = UpnpTestRequester(RESPONSE_MAP)
    factory = UpnpFactory(requester)
    device = await factory.async_create_device("http://ohmedia:1234/device.xml")
    profile = OhmDevice(device, event_handler=None)

    state_var = profile._state_variable("Product", "SourceXml")
    if state_var is not None:
        state_var.value = read_file("SourceXml_test.xml")

    assert profile.has_source_type("Playlist")
    assert not profile.has_source_type("TestSourceNotPresent")


@pytest.mark.asyncio
async def test_async_visible_sources() -> None:
    """Test async_visible_sources."""
    requester = UpnpTestRequester(RESPONSE_MAP)
    factory = UpnpFactory(requester)
    device = await factory.async_create_device("http://ohmedia:1234/device.xml")
    profile = OhmDevice(device, event_handler=None)

    requester.response_map[
        (
            "POST",
            "http://ohmedia:1234/dummy_device_udn/av.openhome.org-Product-4/control",
        )
    ] = HttpResponse(
        200,
        {},
        read_file("response_Product_SourceXml_valid.xml"),
    )

    expected = "[{'Index': 0, 'Name': 'Playlist', 'Type': 'Playlist', 'SystemName': 'Playlist'}, {'Index': 1, 'Name': 'Radio', 'Type': 'Radio', 'SystemName': 'Radio'}]"
    actual = await profile.async_visible_sources()
    assert str(actual) == expected


@pytest.mark.asyncio
async def test_retrieve_state_variable() -> None:
    """Test state variable is returned from service."""

    requester = UpnpTestRequester(RESPONSE_MAP)
    factory = UpnpFactory(requester)
    device = await factory.async_create_device("http://ohmedia:1234/device.xml")
    profile = OhmDevice(device, event_handler=None)
    assert profile.product_source_count is None  # not yet initialised

    product_service = profile.device.service("urn:av-openhome-org:service:Product:4")
    state_var = product_service.state_variable("SourceCount")
    state_var.value = 12  # could be set by polling or subscribing

    assert profile.product_source_count == 12


async def test_get_actions_with_state_variables() -> None:
    """Test for service that all actions returning state variables are returned."""

    requester = UpnpTestRequester(RESPONSE_MAP)
    factory = UpnpFactory(requester)
    device = await factory.async_create_device("http://ohmedia:1234/device.xml")
    profile = OhmDevice(device, event_handler=None)
    actual = profile.get_actions_with_state_variables("Volume")
    expected = {"Mute", "VolumeLimit", "UnityGain", "Fade", "Balance", "Volume", "Characteristics"}
    assert set(actual) == set(expected)


# endregion


# region tests of functions not requiring a profile
def test_decode_id_array() -> None:
    """Test _decode_id_array correctly decodes base64 encoded list."""

    data = "AAAAEwAAABQAAAAVAAAAFgAAABcAAAAdAAAAHgAAAB8="
    assert _decode_id_array(data) == [19, 20, 21, 22, 23, 29, 30, 31]


def test_decode_id_array_empty() -> None:
    """Test _decode_id_array returns empty array on empty input."""

    data = ""
    assert _decode_id_array(data) == []  # pylint: disable=use-implicit-booleaness-not-comparison


def test_decode_id_array_not_an_array() -> None:
    """Test _decode_id_array does not error but returns empty array on bad input."""

    data = "Tm90IGV2ZXIgYW4gQXJyYXk="
    assert _decode_id_array(data) == []  # pylint: disable=use-implicit-booleaness-not-comparison


def test_list_to_string() -> None:
    """Test list converts to space separated string."""

    idlist = [1, 2, 3, 4, 5]
    assert _list_to_string(idlist) == "1 2 3 4 5"
    idlist = []
    assert _list_to_string(idlist) == ""


# endregion
