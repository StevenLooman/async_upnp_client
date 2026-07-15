"""Unit tests for the Linn/Open Home Media profile."""

# pylint: disable=protected-access,line-too-long,too-few-public-methods,too-many-lines

import asyncio
import logging
import os
from collections import deque
from copy import copy, deepcopy
from typing import Mapping, MutableMapping, cast

import pytest
from multidict import CIMultiDict

from async_upnp_client.client import UpnpRequester
from async_upnp_client.client_factory import UpnpFactory
from async_upnp_client.const import HttpRequest, HttpResponse
from async_upnp_client.exceptions import UpnpActionResponseError, UpnpError
from async_upnp_client.profiles.ohmedia import (
    OhmDevice,
    ProductSourceType,
    TransportStateAllowedValues,
    _decode_id_array,
    id_list_to_string,
)

from ..conftest import UpnpTestNotifyServer


class UpnpTestRequester(UpnpRequester):
    """Test requester."""

    def __init__(
        self,
        response_map: Mapping[tuple[str, ...], HttpResponse],
    ) -> None:
        """Class initializer."""
        self.response_map: MutableMapping[tuple[str, ...], HttpResponse] = deepcopy(cast(MutableMapping, response_map))
        self.exceptions: deque[Exception | None] = deque()

    async def async_http_request(
        self,
        http_request: HttpRequest,
    ) -> HttpResponse:
        """Perform an HTTP request."""
        await asyncio.sleep(0.01)
        if self.exceptions:
            exception = self.exceptions.popleft()
            if exception is not None:
                raise exception

        key: tuple[str, ...] = ("",)
        if soap_action := http_request.headers.get("SOAPAction"):
            key = (http_request.method, http_request.url, soap_action.strip('"'))
        else:
            key = (http_request.method, http_request.url)

        if key not in self.response_map:
            raise KeyError(f"Request not in response map: {key}")

        return self.response_map[key]


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

RESPONSE_MAP: Mapping[tuple[str, ...], HttpResponse] = {
    # OpenHomeMedia
    ("GET", "http://ohmedia:1234/device.xml"): HttpResponse(
        200,
        {},
        read_file("device.xml"),
    ),
    ("GET", "http://ohmedia:1234/device_X_no_transport.xml"): HttpResponse(
        200,
        {},
        read_file("device_X_no_transport.xml"),
    ),
    (
        "GET",
        "http://ohmedia:1234/dummy_device_udn/Upnp/av.openhome.org-ConfigApp-1/service.xml",
    ): HttpResponse(
        200,
        {},
        read_file("Config1_service.xml"),
    ),
    (
        "GET",
        "http://ohmedia:1234/dummy_device_udn/Upnp/av.openhome.org-Product-4/service.xml",
    ): HttpResponse(
        200,
        {},
        read_file("Product4_service.xml"),
    ),
    (
        "GET",
        "http://ohmedia:1234/dummy_device_udn/Upnp/av.openhome.org-Volume-4/service.xml",
    ): HttpResponse(
        200,
        {},
        read_file("Volume4_service.xml"),
    ),
    (
        "GET",
        "http://ohmedia:1234/dummy_device_udn/Upnp/av.openhome.org-Playlist-1/service.xml",
    ): HttpResponse(
        200,
        {},
        read_file("Playlist1_service.xml"),
    ),
    (
        "GET",
        "http://ohmedia:1234/dummy_device_udn/Upnp/av.openhome.org-Radio-1/service.xml",
    ): HttpResponse(
        200,
        {},
        read_file("Radio1_service.xml"),
    ),
    (
        "GET",
        "http://ohmedia:1234/dummy_device_udn/Upnp/av.openhome.org-Transport-1/service.xml",
    ): HttpResponse(
        200,
        {},
        read_file("Transport1_service.xml"),
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
        "SUBSCRIBE",
        "http://ohmedia:1234/dummy_device_udn/av.openhome.org-Transport-1/event",
    ): HttpResponse(
        200,
        {"sid": "uuid:dummy-transport-1", "timeout": "Second-300"},
        "",
    ),
    (
        "SUBSCRIBE",
        "http://ohmedia:1234/dummy_device_udn/av.openhome.org-Radio-1/event",
    ): HttpResponse(
        200,
        {"sid": "uuid:dummy-radio-1", "timeout": "Second-300"},
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
    (
        "UNSUBSCRIBE",
        "http://ohmedia:1234/dummy_device_udn/av.openhome.org-Transport-1/event",
    ): HttpResponse(
        200,
        {"sid": "uuid:dummy-transport-1"},
        "",
    ),
    (
        "UNSUBSCRIBE",
        "http://ohmedia:1234/dummy_device_udn/av.openhome.org-Radio-1/event",
    ): HttpResponse(
        200,
        {"sid": "uuid:dummy-radio-1"},
        "",
    ),
    (
        "POST",
        "http://ohmedia:1234/dummy_device_udn/av.openhome.org-Product-4/control",
        "urn:av-openhome-org:service:Product:4#SourceIndex",
    ): HttpResponse(
        200,
        {},
        read_file("Product_SourceIndexResponse.xml"),
    ),
    (
        "POST",
        "http://ohmedia:1234/dummy_device_udn/av.openhome.org-Product-4/control",
        "urn:av-openhome-org:service:Product:4#Source",
    ): HttpResponse(
        200,
        {},
        read_file("Product_SourceResponse.xml"),
    ),
    (
        "POST",
        "http://ohmedia:1234/dummy_device_udn/av.openhome.org-Volume-4/control",
        "urn:av-openhome-org:service:Volume:4#SetMute",
    ): HttpResponse(
        200,
        {},
        read_file("Volume_SetMuteResponse.xml"),
    ),
}


# region profile tests
@pytest.mark.asyncio
async def test_instantiate_ohmdevice_no_handler() -> None:
    """Test can instantiate a profile object of OhmDevice."""
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
            "urn:av-openhome-org:service:Volume:4#Volume",
        )
    ] = HttpResponse(
        200,
        {},
        read_file("Volume_VolumeResponse.xml"),
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
            "urn:av-openhome-org:service:Playlist:1#IdArrayChanged",
        )
    ] = HttpResponse(
        200,
        {},
        read_file("Playlist_IdArrayChangedResponse.xml"),
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
            "urn:av-openhome-org:service:Playlist:1#Insert",
        )
    ] = HttpResponse(
        200,
        {},
        read_file("Playlist_InsertResponse.xml"),
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
    with pytest.raises(UpnpError):
        await profile._async_call_action("NoService", "Action")


@pytest.mark.asyncio
async def test_async_call_action_bad_action() -> None:
    """Test _async_call_action with non-existent action for service."""
    requester = UpnpTestRequester(RESPONSE_MAP)
    factory = UpnpFactory(requester)
    device = await factory.async_create_device("http://ohmedia:1234/device.xml")
    profile = OhmDevice(device, event_handler=None)
    with pytest.raises(UpnpError):
        await profile._async_call_action("Volume", "NonexistentAction")


@pytest.mark.asyncio
async def test_async_call_action_bad_param_value() -> None:
    """Test _async_call_action with no kwargs."""
    requester = UpnpTestRequester(RESPONSE_MAP)
    factory = UpnpFactory(requester)
    device = await factory.async_create_device("http://ohmedia:1234/device.xml")
    profile = OhmDevice(device, event_handler=None)

    requester.response_map[
        (
            "POST",
            "http://ohmedia:1234/dummy_device_udn/av.openhome.org-Playlist-1/control",
            "urn:av-openhome-org:service:Playlist:1#DeleteId",
        )
    ] = HttpResponse(
        500,
        {},
        read_file("Playlist_DeleteId_X_Id_Not_Found.xml"),
    )
    with pytest.raises(UpnpActionResponseError) as exinfo:  # call action expecting 800 upnp error
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
            "urn:av-openhome-org:service:Product:4#SourceXml",
        )
    ] = HttpResponse(
        200,
        {},
        read_file("Product_SourceXmlResponse.xml"),
    )

    expected = {
        "Value": "<SourceList><Source><Name>Playlist</Name><Type>Playlist</Type><Visible>true</Visible><SystemName>Playlist</SystemName></Source><Source><Name>Radio</Name><Type>Radio</Type><Visible>true</Visible><SystemName>Radio</SystemName></Source><Source><Name>UPnP</Name><Type>UpnpAv</Type><Visible>false</Visible><SystemName>UPnP AV</SystemName></Source></SourceList>"
    }
    actual = await profile._async_call_action("Product", "SourceXml")
    assert actual == expected


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

    device_X_no_volume.xml modified so that no Volume service is advertised
    """

    requester = UpnpTestRequester(RESPONSE_MAP)
    requester.response_map[("GET", "http://ohmedia:1234/device_X_no_volume.xml")] = HttpResponse(
        200,
        {},
        read_file("device_X_no_volume.xml"),
    )
    factory = UpnpFactory(requester)
    device = await factory.async_create_device("http://ohmedia:1234/device_X_no_volume.xml")
    profile = OhmDevice(device, event_handler=None)

    assert not profile.has_volume


@pytest.mark.asyncio
async def test_has_product_standby_when_action_not_present() -> None:
    """Test has_product_standby returns False when action is not present.

    device_X_no_standby.xml fixture modified to request Product4_service_X_no_standby.xml for Product4 service.xml
    Product4_service_X_no_standby.xml fixture modified so that Standby action is not present
    """

    requester = UpnpTestRequester(RESPONSE_MAP)
    requester.response_map[("GET", "http://ohmedia:1234/device_X_no_standby.xml")] = HttpResponse(
        200,
        {},
        read_file("device_X_no_standby.xml"),
    )
    requester.response_map[
        (
            "GET",
            "http://ohmedia:1234/dummy_device_udn/Upnp/av.openhome.org-Product-4/Product4_service_X_no_standby.xml",
        )
    ] = HttpResponse(
        200,
        {},
        read_file("Product4_service_X_no_standby.xml"),
    )
    factory = UpnpFactory(requester)
    device = await factory.async_create_device("http://ohmedia:1234/device_X_no_standby.xml")
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
        state_var.value = read_file("Product_SourceXml_sv.xml")

    assert profile.has_source_type(ProductSourceType.PLAYLIST)
    assert not profile.has_source_type(ProductSourceType.NETAUX)


@pytest.mark.asyncio
async def test_has_source_type_no_sv() -> None:
    """Test has_source_type returns None if SourceXml is not populated."""

    requester = UpnpTestRequester(RESPONSE_MAP)
    factory = UpnpFactory(requester)
    device = await factory.async_create_device("http://ohmedia:1234/device.xml")
    profile = OhmDevice(device, event_handler=None)

    assert profile.has_source_type(ProductSourceType.PLAYLIST) is None


@pytest.mark.asyncio
async def test_has_source_type_log_error(caplog: pytest.LogCaptureFixture) -> None:
    """Test has_source_type ignores ParseError exception, returns None and logs error."""

    caplog.set_level(logging.ERROR)
    requester = UpnpTestRequester(RESPONSE_MAP)
    factory = UpnpFactory(requester)
    device = await factory.async_create_device("http://ohmedia:1234/device.xml")
    profile = OhmDevice(device, event_handler=None)

    state_var = profile._state_variable("Product", "SourceXml")
    if state_var is not None:
        state_var.value = read_file("Product_SourceXml_sv_X_malformed.xml")

    assert profile.has_source_type(ProductSourceType.PLAYLIST) is None
    assert "source_xml is not valid" in caplog.text


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
            "urn:av-openhome-org:service:Product:4#SourceXml",
        )
    ] = HttpResponse(
        200,
        {},
        read_file("Product_SourceXmlResponse.xml"),
    )

    expected = [
        {"Index": 0, "Name": "Playlist", "Type": "Playlist", "SystemName": "Playlist"},
        {"Index": 1, "Name": "Radio", "Type": "Radio", "SystemName": "Radio"},
    ]
    actual = await profile.async_visible_sources()
    assert actual == expected


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


@pytest.mark.asyncio
async def test_get_actions_with_state_variables() -> None:
    """Test for service that all actions returning state variables are returned."""

    requester = UpnpTestRequester(RESPONSE_MAP)
    factory = UpnpFactory(requester)
    device = await factory.async_create_device("http://ohmedia:1234/device.xml")
    profile = OhmDevice(device, event_handler=None)
    actual = profile.get_actions_with_state_variables("Volume")
    expected = {"Mute", "VolumeLimit", "UnityGain", "Fade", "Balance", "Volume", "Characteristics"}
    assert set(actual) == set(expected)


@pytest.mark.asyncio
async def test_async_active_source_index() -> None:
    """Test async_active_source_index."""

    requester = UpnpTestRequester(RESPONSE_MAP)
    factory = UpnpFactory(requester)
    device = await factory.async_create_device("http://ohmedia:1234/device.xml")
    profile = OhmDevice(device, event_handler=None)

    actual = await profile.async_active_source_index()
    expected = 11
    assert actual == expected


@pytest.mark.asyncio
async def test_async_product_source() -> None:
    """Test async_active_source_index."""

    requester = UpnpTestRequester(RESPONSE_MAP)
    factory = UpnpFactory(requester)
    device = await factory.async_create_device("http://ohmedia:1234/device.xml")
    profile = OhmDevice(device, event_handler=None)

    actual = await profile.async_product_source(index=0)  # test fixture is not parameterised by index
    expected = {"Name": "TV", "SystemName": "TOSLINK1", "Type": "Digital", "Visible": True}
    assert actual == expected


@pytest.mark.asyncio
async def test_async_playlist_last_id() -> None:
    """Test async_playlist_last_id."""

    requester = UpnpTestRequester(RESPONSE_MAP)
    factory = UpnpFactory(requester)
    device = await factory.async_create_device("http://ohmedia:1234/device.xml")
    profile = OhmDevice(device, event_handler=None)

    requester.response_map[
        (
            "POST",
            "http://ohmedia:1234/dummy_device_udn/av.openhome.org-Playlist-1/control",
            "urn:av-openhome-org:service:Playlist:1#IdArray",
        )
    ] = HttpResponse(
        200,
        {},
        read_file("Playlist_IdArrayResponse.xml"),
    )

    actual = await profile.async_playlist_last_id()
    expected = 20
    assert actual == expected


@pytest.mark.asyncio
async def test_volume() -> None:
    """Test volume."""

    requester = UpnpTestRequester(RESPONSE_MAP)
    factory = UpnpFactory(requester)
    device = await factory.async_create_device("http://ohmedia:1234/device.xml")
    profile = OhmDevice(device, event_handler=None)

    state_var = profile._state_variable("Volume", "Volume")
    if state_var:
        state_var.value = 40

    actual_volume = profile.volume
    assert actual_volume == 40


@pytest.mark.asyncio
async def test_async_active_source() -> None:
    """Test async_active_source."""

    requester = UpnpTestRequester(RESPONSE_MAP)
    factory = UpnpFactory(requester)
    device = await factory.async_create_device("http://ohmedia:1234/device.xml")
    profile = OhmDevice(device, event_handler=None)

    expected_source = {"Name": "TV", "SystemName": "TOSLINK1", "Type": "Digital", "Visible": True}
    actual_source = await profile.async_active_source()
    assert actual_source == expected_source


@pytest.mark.asyncio
async def test_async_active_source_name() -> None:
    """Test async_active_source_name."""

    requester = UpnpTestRequester(RESPONSE_MAP)
    factory = UpnpFactory(requester)
    device = await factory.async_create_device("http://ohmedia:1234/device.xml")
    profile = OhmDevice(device, event_handler=None)

    expected_name = "TV"
    actual_name = await profile.async_active_source_name()
    assert actual_name == expected_name


@pytest.mark.asyncio
async def test_async_active_source_type() -> None:
    """Test async_active_source_type."""

    requester = UpnpTestRequester(RESPONSE_MAP)
    factory = UpnpFactory(requester)
    device = await factory.async_create_device("http://ohmedia:1234/device.xml")
    profile = OhmDevice(device, event_handler=None)

    expected_type = "Digital"
    actual_type = await profile.async_active_source_type()
    assert actual_type == expected_type


@pytest.mark.asyncio
async def test_async_volume_set_mute() -> None:
    """Test async_volume_set_mute."""
    requester = UpnpTestRequester(RESPONSE_MAP)
    factory = UpnpFactory(requester)
    device = await factory.async_create_device("http://ohmedia:1234/device.xml")
    profile = OhmDevice(device, event_handler=None)

    await profile.async_volume_set_mute(True)


@pytest.mark.asyncio
async def test_async_volume_set_mute_not_bool() -> None:
    """Test async_volume_set_mute.

    Calling with other than bool raises a TypeError
    """
    requester = UpnpTestRequester(RESPONSE_MAP)
    factory = UpnpFactory(requester)
    device = await factory.async_create_device("http://ohmedia:1234/device.xml")
    profile = OhmDevice(device, event_handler=None)

    with pytest.raises(TypeError):
        await profile.async_volume_set_mute("True")  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        await profile.async_volume_set_mute(0)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_transport_state() -> None:
    """Test transport_state.

    Test TransportState property when Transport Service is available
    """
    requester = UpnpTestRequester(RESPONSE_MAP)
    factory = UpnpFactory(requester)
    device = await factory.async_create_device("http://ohmedia:1234/device.xml")
    profile = OhmDevice(device, event_handler=None)

    transport_state = profile._state_variable("Transport", "TransportState")
    assert transport_state is not None
    transport_state.value = TransportStateAllowedValues.PLAYING.value

    actual = profile.transport_state
    assert actual == "Playing"


@pytest.mark.asyncio
async def test_transport_state_no_transport_service() -> None:
    """Test transport_state when no TransportService is available.

    Test TransportState property when Transport Service is not available
    Transport State returned should be that of active source
    """
    requester = UpnpTestRequester(RESPONSE_MAP)
    factory = UpnpFactory(requester)
    device = await factory.async_create_device("http://ohmedia:1234/device_X_no_transport.xml")
    profile = OhmDevice(device, event_handler=None)

    # set source xml to have Playlist and Radio available as sources
    product_source_xml = profile._state_variable("Product", "SourceXml")
    assert product_source_xml is not None
    product_source_xml.value = read_file("Product_SourceXml_TransportState.xml")
    assert product_source_xml.value is not None

    # create source index sv
    product_source_index = profile._state_variable("Product", "SourceIndex")
    assert product_source_index is not None

    product_source_index.value = 0  # set active source as Playlist
    playlist_transport_state = profile._state_variable("Playlist", "TransportState")
    assert playlist_transport_state is not None
    playlist_transport_state.value = "Playing"

    actual = profile.transport_state
    assert actual == "Playing"

    product_source_index.value = 1  # set active source as Radio
    radio_transport_state = profile._state_variable("Radio", "TransportState")
    assert radio_transport_state is not None
    radio_transport_state.value = "Stopped"

    actual = profile.transport_state
    assert actual == "Stopped"


@pytest.mark.asyncio
async def test_transport_state_parse_error(caplog: pytest.LogCaptureFixture) -> None:
    """Test transport_state when malformed source xml ParseError is caught."""

    caplog.set_level(logging.ERROR)
    requester = UpnpTestRequester(RESPONSE_MAP)
    factory = UpnpFactory(requester)
    device = await factory.async_create_device("http://ohmedia:1234/device_X_no_transport.xml")
    profile = OhmDevice(device, event_handler=None)

    # set source xml to malformed
    product_source_xml = profile._state_variable("Product", "SourceXml")
    assert product_source_xml is not None
    product_source_xml.value = read_file("Product_SourceXml_sv_X_malformed.xml")
    assert product_source_xml.value is not None

    playlist_transport_state = profile._state_variable("Playlist", "TransportState")
    assert playlist_transport_state is not None
    playlist_transport_state.value = "Playing"

    # don't raise error (because @property) but do log error
    actual = profile.transport_state
    assert actual is None
    assert "Value is not valid XML" in caplog.text


@pytest.mark.asyncio
async def test_transport_state_no_source_index(caplog: pytest.LogCaptureFixture) -> None:
    """Test transport_state when active source type is not handled."""
    caplog.set_level(logging.WARNING)
    requester = UpnpTestRequester(RESPONSE_MAP)
    factory = UpnpFactory(requester)
    device = await factory.async_create_device("http://ohmedia:1234/device_X_no_transport.xml")
    profile = OhmDevice(device, event_handler=None)

    product_source_index = profile._state_variable("Product", "SourceIndex")
    assert product_source_index is not None
    assert product_source_index.value is None

    # don't raise error (because @property) but do log error
    assert profile.transport_state is None
    assert "Unhandled source type" in caplog.text


@pytest.mark.asyncio
async def test_transport_state_unhandled_source_type(caplog: pytest.LogCaptureFixture) -> None:
    """Test transport_state when active source type is not handled."""
    caplog.set_level(logging.WARNING)
    requester = UpnpTestRequester(RESPONSE_MAP)
    factory = UpnpFactory(requester)
    device = await factory.async_create_device("http://ohmedia:1234/device_X_no_transport.xml")
    profile = OhmDevice(device, event_handler=None)

    product_source_index = profile._state_variable("Product", "SourceIndex")
    assert product_source_index is not None
    product_source_index.value = 2  # set active source as UpnpAv

    # don't raise error (because @property) but do log error
    assert profile.transport_state is None
    assert "Unhandled source type" in caplog.text


@pytest.mark.asyncio
async def test_async_play() -> None:
    """Test async_play.

    Using Transport Service Play
    """
    requester = UpnpTestRequester(RESPONSE_MAP)
    factory = UpnpFactory(requester)
    device = await factory.async_create_device("http://ohmedia:1234/device.xml")
    profile = OhmDevice(device, event_handler=None)

    requester.response_map[
        (
            "POST",
            "http://ohmedia:1234/dummy_device_udn/av.openhome.org-Transport-1/control",
            "urn:av-openhome-org:service:Transport:1#Play",
        )
    ] = HttpResponse(
        200,
        {},
        read_file("Transport1_PlayResponse.xml"),
    )

    await profile.async_play()


@pytest.mark.asyncio
async def test_async_pause() -> None:
    """Test async_pause."""
    requester = UpnpTestRequester(RESPONSE_MAP)
    factory = UpnpFactory(requester)
    device = await factory.async_create_device("http://ohmedia:1234/device.xml")
    profile = OhmDevice(device, event_handler=None)

    requester.response_map[
        (
            "POST",
            "http://ohmedia:1234/dummy_device_udn/av.openhome.org-Transport-1/control",
            "urn:av-openhome-org:service:Transport:1#Pause",
        )
    ] = HttpResponse(
        200,
        {},
        read_file("Transport1_PauseResponse.xml"),
    )

    await profile.async_pause()


@pytest.mark.asyncio
async def test_async_stop() -> None:
    """Test async_stop."""
    requester = UpnpTestRequester(RESPONSE_MAP)
    factory = UpnpFactory(requester)
    device = await factory.async_create_device("http://ohmedia:1234/device.xml")
    profile = OhmDevice(device, event_handler=None)

    requester.response_map[
        (
            "POST",
            "http://ohmedia:1234/dummy_device_udn/av.openhome.org-Transport-1/control",
            "urn:av-openhome-org:service:Transport:1#Stop",
        )
    ] = HttpResponse(
        200,
        {},
        read_file("Transport1_StopResponse.xml"),
    )

    await profile.async_stop()


@pytest.mark.asyncio
async def test_async_play_no_transport_service() -> None:
    """Test async_play when Transport service is not available."""
    requester = UpnpTestRequester(RESPONSE_MAP)
    factory = UpnpFactory(requester)
    device = await factory.async_create_device("http://ohmedia:1234/device_X_no_transport.xml")
    profile = OhmDevice(device, event_handler=None)

    requester.response_map.update(
        {
            (
                "POST",
                "http://ohmedia:1234/dummy_device_udn/av.openhome.org-Product-4/control",
                "urn:av-openhome-org:service:Product:4#Source",
            ): HttpResponse(
                200,
                {},
                read_file("Product_SourceResponse_Playlist.xml"),
            ),
            (
                "POST",
                "http://ohmedia:1234/dummy_device_udn/av.openhome.org-Playlist-1/control",
                "urn:av-openhome-org:service:Playlist:1#Play",
            ): HttpResponse(
                200,
                {},
                read_file("Playlist_PlayResponse.xml"),
            ),
        }
    )

    await profile.async_play()


@pytest.mark.asyncio
async def test_async_pause_no_transport_service() -> None:
    """Test async_pause when Transport service is not available."""
    requester = UpnpTestRequester(RESPONSE_MAP)
    factory = UpnpFactory(requester)
    device = await factory.async_create_device("http://ohmedia:1234/device_X_no_transport.xml")
    profile = OhmDevice(device, event_handler=None)

    requester.response_map.update(
        {
            (
                "POST",
                "http://ohmedia:1234/dummy_device_udn/av.openhome.org-Product-4/control",
                "urn:av-openhome-org:service:Product:4#Source",
            ): HttpResponse(
                200,
                {},
                read_file("Product_SourceResponse_Playlist.xml"),
            ),
            (
                "POST",
                "http://ohmedia:1234/dummy_device_udn/av.openhome.org-Playlist-1/control",
                "urn:av-openhome-org:service:Playlist:1#Pause",
            ): HttpResponse(
                200,
                {},
                read_file("Playlist_PauseResponse.xml"),
            ),
        }
    )

    await profile.async_pause()


@pytest.mark.asyncio
async def test_async_stop_no_transport_service() -> None:
    """Test async_stop when Transport service is not available."""
    requester = UpnpTestRequester(RESPONSE_MAP)
    factory = UpnpFactory(requester)
    device = await factory.async_create_device("http://ohmedia:1234/device_X_no_transport.xml")
    profile = OhmDevice(device, event_handler=None)

    requester.response_map.update(
        {
            (
                "POST",
                "http://ohmedia:1234/dummy_device_udn/av.openhome.org-Product-4/control",
                "urn:av-openhome-org:service:Product:4#Source",
            ): HttpResponse(
                200,
                {},
                read_file("Product_SourceResponse_Playlist.xml"),
            ),
            (
                "POST",
                "http://ohmedia:1234/dummy_device_udn/av.openhome.org-Playlist-1/control",
                "urn:av-openhome-org:service:Playlist:1#Stop",
            ): HttpResponse(
                200,
                {},
                read_file("Playlist_StopResponse.xml"),
            ),
        }
    )

    await profile.async_stop()


@pytest.mark.asyncio
async def test_async_play_no_transport_service_unhandled(caplog: pytest.LogCaptureFixture) -> None:
    """Test async_play when Transport service is not available and source is unhandled."""

    caplog.set_level(logging.WARNING)
    requester = UpnpTestRequester(RESPONSE_MAP)
    factory = UpnpFactory(requester)
    device = await factory.async_create_device("http://ohmedia:1234/device_X_no_transport.xml")
    profile = OhmDevice(device, event_handler=None)

    requester.response_map.update(
        {
            (
                "POST",
                "http://ohmedia:1234/dummy_device_udn/av.openhome.org-Product-4/control",
                "urn:av-openhome-org:service:Product:4#Source",
            ): HttpResponse(
                200,
                {},
                read_file("Product_SourceResponse.xml"),  # Source is Digital hence unhandled
            ),
        }
    )

    await profile.async_play()
    assert "Unhandled source type" in caplog.text


@pytest.mark.asyncio
async def test_async_stop_while_stopped() -> None:
    """Test async_stop when transport state is Stopped."""
    requester = UpnpTestRequester(RESPONSE_MAP)
    factory = UpnpFactory(requester)
    device = await factory.async_create_device("http://ohmedia:1234/device.xml")
    profile = OhmDevice(device, event_handler=None)

    # Transport Service Stop must not be configured, so error will be raised if it is called
    # Test passes if Transport Service Stop is NOT called and so no error is raised
    transport_state = profile._state_variable("Transport", "TransportState")
    assert transport_state is not None
    transport_state.value = "Stopped"
    assert profile.transport_state == "Stopped"

    await profile.async_stop()

    @pytest.mark.asyncio
    async def test_async_pause_while_stopped() -> None:
        """Test async_pause when transport state is Stopped."""
        requester = UpnpTestRequester(RESPONSE_MAP)
        factory = UpnpFactory(requester)
        device = await factory.async_create_device("http://ohmedia:1234/device.xml")
        profile = OhmDevice(device, event_handler=None)

        # Transport Service Pause must not be configured, so error will be raised if it is called
        # Test passes if Transport Service Stop is NOT called and so no error is raised
        transport_state = profile._state_variable("Transport", "TransportState")
        assert transport_state is not None
        transport_state.value = "Stopped"
        assert profile.transport_state == "Stopped"

        await profile.async_pause()


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


def test_id_list_to_string() -> None:
    """Test list converts to space separated string."""

    idlist = [1, 2, 3, 4, 5]
    assert id_list_to_string(idlist) == "1 2 3 4 5"
    idlist = []
    assert id_list_to_string(idlist) == ""


# endregion
