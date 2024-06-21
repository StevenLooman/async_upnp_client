# -*- coding: utf-8 -*-
"""Unit tests for client_factory and client modules."""

from datetime import datetime, timedelta, timezone
from typing import MutableMapping

import defusedxml.ElementTree as DET
import pytest

from async_upnp_client.client import UpnpStateVariable
from async_upnp_client.client_factory import UpnpFactory
from async_upnp_client.const import HttpResponse
from async_upnp_client.exceptions import (
    UpnpActionError,
    UpnpActionErrorCode,
    UpnpActionResponseError,
    UpnpError,
    UpnpResponseError,
    UpnpValueError,
    UpnpXmlContentError,
    UpnpXmlParseError,
)

from .conftest import RESPONSE_MAP, UpnpTestRequester, read_file


class TestUpnpStateVariable:
    """Tests for UpnpStateVariable."""

    @pytest.mark.asyncio
    async def test_init(self) -> None:
        """Test initialization of a UpnpDevice."""
        requester = UpnpTestRequester(RESPONSE_MAP)
        factory = UpnpFactory(requester)
        device = await factory.async_create_device("http://dlna_dmr:1234/device.xml")
        assert device
        assert device.device_type == "urn:schemas-upnp-org:device:MediaRenderer:1"

        service = device.service("urn:schemas-upnp-org:service:RenderingControl:1")
        assert service

        service_by_id = device.service_id("urn:upnp-org:serviceId:RenderingControl")
        assert service_by_id == service

        state_var = service.state_variable("Volume")
        assert state_var

        action = service.action("GetVolume")
        assert action

        argument = action.argument("InstanceID")
        assert argument

    @pytest.mark.asyncio
    async def test_init_embedded_device(self) -> None:
        """Test initialization of a embedded UpnpDevice."""
        requester = UpnpTestRequester(RESPONSE_MAP)
        factory = UpnpFactory(requester)
        device = await factory.async_create_device("http://igd:1234/device.xml")
        assert device
        assert (
            device.device_type == "urn:schemas-upnp-org:device:InternetGatewayDevice:1"
        )

        embedded_device = device.embedded_devices[
            "urn:schemas-upnp-org:device:WANDevice:1"
        ]
        assert embedded_device
        assert embedded_device.device_type == "urn:schemas-upnp-org:device:WANDevice:1"
        assert embedded_device.parent_device == device

    @pytest.mark.asyncio
    async def test_init_xml(self) -> None:
        """Test XML is stored on every part of the UpnpDevice."""
        requester = UpnpTestRequester(RESPONSE_MAP)
        factory = UpnpFactory(requester)
        device = await factory.async_create_device("http://dlna_dmr:1234/device.xml")
        assert device.xml is not None

        service = device.service("urn:schemas-upnp-org:service:RenderingControl:1")
        assert service.xml is not None

        state_var = service.state_variable("Volume")
        assert state_var.xml is not None

        action = service.action("GetVolume")
        assert action.xml is not None

        argument = action.argument("InstanceID")
        assert argument is not None
        assert argument.xml is not None

    @pytest.mark.asyncio
    async def test_init_bad_xml(self) -> None:
        """Test missing device element in device description."""
        responses = dict(RESPONSE_MAP)
        responses[("GET", "http://dlna_dmr:1234/device.xml")] = HttpResponse(
            200,
            {},
            read_file("dlna/dmr/device_bad_namespace.xml"),
        )
        requester = UpnpTestRequester(responses)
        factory = UpnpFactory(requester)
        with pytest.raises(UpnpXmlContentError):
            await factory.async_create_device("http://dlna_dmr:1234/device.xml")

    @pytest.mark.asyncio
    async def test_empty_descriptor(self) -> None:
        """Test device with an empty descriptor file called in description.xml."""
        responses = dict(RESPONSE_MAP)
        responses[("GET", "http://dlna_dmr:1234/device.xml")] = HttpResponse(
            200,
            {},
            read_file("dlna/dmr/device_with_empty_descriptor.xml"),
        )
        requester = UpnpTestRequester(responses)
        factory = UpnpFactory(requester)
        with pytest.raises(UpnpXmlParseError):
            await factory.async_create_device("http://dlna_dmr:1234/device.xml")

    @pytest.mark.asyncio
    async def test_empty_descriptor_non_strict(self) -> None:
        """Test device with an empty descriptor file called in description.xml."""
        responses = dict(RESPONSE_MAP)
        responses[("GET", "http://dlna_dmr:1234/device.xml")] = HttpResponse(
            200,
            {},
            read_file("dlna/dmr/device_with_empty_descriptor.xml"),
        )
        requester = UpnpTestRequester(responses)
        factory = UpnpFactory(requester, non_strict=True)
        await factory.async_create_device("http://dlna_dmr:1234/device.xml")

    @pytest.mark.asyncio
    async def test_set_value_volume(self) -> None:
        """Test calling parsing/reading values from UpnpStateVariable."""
        requester = UpnpTestRequester(RESPONSE_MAP)
        factory = UpnpFactory(requester)
        device = await factory.async_create_device("http://dlna_dmr:1234/device.xml")
        service = device.service("urn:schemas-upnp-org:service:RenderingControl:1")
        state_var = service.state_variable("Volume")

        state_var.value = 10
        assert state_var.value == 10
        assert state_var.upnp_value == "10"

        state_var.upnp_value = "20"
        assert state_var.value == 20
        assert state_var.upnp_value == "20"

    @pytest.mark.asyncio
    async def test_set_value_mute(self) -> None:
        """Test setting a boolean value."""
        requester = UpnpTestRequester(RESPONSE_MAP)
        factory = UpnpFactory(requester)
        device = await factory.async_create_device("http://dlna_dmr:1234/device.xml")
        service = device.service("urn:schemas-upnp-org:service:RenderingControl:1")
        state_var = service.state_variable("Mute")

        state_var.value = True
        assert state_var.value is True
        assert state_var.upnp_value == "1"

        state_var.value = False
        assert state_var.value is False
        assert state_var.upnp_value == "0"

        state_var.upnp_value = "1"
        assert state_var.value is True
        assert state_var.upnp_value == "1"

        state_var.upnp_value = "0"
        assert state_var.value is False
        assert state_var.upnp_value == "0"

    @pytest.mark.asyncio
    async def test_value_min_max(self) -> None:
        """Test min/max restrictions."""
        requester = UpnpTestRequester(RESPONSE_MAP)
        factory = UpnpFactory(requester)
        device = await factory.async_create_device("http://dlna_dmr:1234/device.xml")
        service = device.service("urn:schemas-upnp-org:service:RenderingControl:1")
        state_var = service.state_variable("Volume")

        assert state_var.min_value == 0
        assert state_var.max_value == 100

        state_var.value = 10
        assert state_var.value == 10

        try:
            state_var.value = -10
            assert False
        except UpnpValueError:
            pass

        try:
            state_var.value = 110
            assert False
        except UpnpValueError:
            pass

    @pytest.mark.asyncio
    async def test_value_min_max_validation_disable(self) -> None:
        """Test if min/max validations can be disabled."""
        requester = UpnpTestRequester(RESPONSE_MAP)
        factory = UpnpFactory(requester, non_strict=True)
        device = await factory.async_create_device("http://dlna_dmr:1234/device.xml")
        service = device.service("urn:schemas-upnp-org:service:RenderingControl:1")
        state_var = service.state_variable("Volume")

        # min/max are set
        assert state_var.min_value == 0
        assert state_var.max_value == 100

        # min/max are not validated
        state_var.value = -10
        assert state_var.value == -10

        state_var.value = 110
        assert state_var.value == 110

    @pytest.mark.asyncio
    async def test_value_allowed_value(self) -> None:
        """Test handling allowed values."""
        requester = UpnpTestRequester(RESPONSE_MAP)
        factory = UpnpFactory(requester)
        device = await factory.async_create_device("http://dlna_dmr:1234/device.xml")
        service = device.service("urn:schemas-upnp-org:service:RenderingControl:1")
        state_var = service.state_variable("A_ARG_TYPE_Channel")

        assert state_var.allowed_values == {"Master"}
        assert state_var.normalized_allowed_values == {"master"}

        # should be ok
        state_var.value = "Master"
        assert state_var.value == "Master"

        try:
            state_var.value = "Left"
            assert False
        except UpnpValueError:
            pass

    @pytest.mark.asyncio
    async def test_value_upnp_value_error(self) -> None:
        """Test handling invalid values in response."""
        requester = UpnpTestRequester(RESPONSE_MAP)
        factory = UpnpFactory(requester, non_strict=True)
        device = await factory.async_create_device("http://dlna_dmr:1234/device.xml")
        service = device.service("urn:schemas-upnp-org:service:RenderingControl:1")
        state_var = service.state_variable("Volume")

        # should be ok
        state_var.upnp_value = "50"
        assert state_var.value == 50

        # should set UpnpStateVariable.UPNP_VALUE_ERROR
        state_var.upnp_value = "abc"
        assert state_var.value is None
        assert state_var.value_unchecked is UpnpStateVariable.UPNP_VALUE_ERROR

    @pytest.mark.asyncio
    async def test_value_date_time(self) -> None:
        """Test parsing of datetime."""
        requester = UpnpTestRequester(RESPONSE_MAP)
        factory = UpnpFactory(requester, non_strict=True)
        device = await factory.async_create_device("http://dlna_dmr:1234/device.xml")
        service = device.service("urn:schemas-upnp-org:service:RenderingControl:1")
        state_var = service.state_variable("SV1")

        # should be ok
        state_var.upnp_value = "1985-04-12T10:15:30"
        assert state_var.value == datetime(1985, 4, 12, 10, 15, 30)

    @pytest.mark.asyncio
    async def test_value_date_time_tz(self) -> None:
        """Test parsing of date_time with a timezone."""
        requester = UpnpTestRequester(RESPONSE_MAP)
        factory = UpnpFactory(requester, non_strict=True)
        device = await factory.async_create_device("http://dlna_dmr:1234/device.xml")
        service = device.service("urn:schemas-upnp-org:service:RenderingControl:1")
        state_var = service.state_variable("SV2")
        assert state_var is not None

        # should be ok
        state_var.upnp_value = "1985-04-12T10:15:30+0400"
        assert state_var.value == datetime(
            1985, 4, 12, 10, 15, 30, tzinfo=timezone(timedelta(hours=4))
        )
        assert state_var.value.tzinfo is not None

    @pytest.mark.asyncio
    async def test_send_events(self) -> None:
        """Test if send_events is properly handled."""
        requester = UpnpTestRequester(RESPONSE_MAP)
        factory = UpnpFactory(requester)
        device = await factory.async_create_device("http://dlna_dmr:1234/device.xml")
        service = device.service("urn:schemas-upnp-org:service:RenderingControl:1")

        state_var = service.state_variable("A_ARG_TYPE_InstanceID")  # old style
        assert state_var.send_events is False

        state_var = service.state_variable("A_ARG_TYPE_Channel")  # new style
        assert state_var.send_events is False

        state_var = service.state_variable("Volume")  # broken/none given
        assert state_var.send_events is False

        state_var = service.state_variable("LastChange")
        assert state_var.send_events is True

    @pytest.mark.asyncio
    async def test_big_ints(self) -> None:
        """Test state variable types i8 and ui8."""
        responses = dict(RESPONSE_MAP)
        responses[("GET", "http://dlna_dms:1234/ContentDirectory_1.xml")] = (
            HttpResponse(
                200,
                {},
                read_file("scpd_i8.xml"),
            )
        )
        requester = UpnpTestRequester(responses)
        factory = UpnpFactory(requester)
        device = await factory.async_create_device("http://dlna_dms:1234/device.xml")
        assert device is not None


class TestUpnpAction:
    """Tests for UpnpAction."""

    @pytest.mark.asyncio
    async def test_init(self) -> None:
        """Test Initializing a UpnpAction."""
        requester = UpnpTestRequester(RESPONSE_MAP)
        factory = UpnpFactory(requester)
        device = await factory.async_create_device("http://dlna_dmr:1234/device.xml")
        service = device.service("urn:schemas-upnp-org:service:RenderingControl:1")
        action = service.action("GetVolume")

        assert action
        assert action.name == "GetVolume"

    @pytest.mark.asyncio
    async def test_valid_arguments(self) -> None:
        """Test validating arguments of an action."""
        requester = UpnpTestRequester(RESPONSE_MAP)
        factory = UpnpFactory(requester)
        device = await factory.async_create_device("http://dlna_dmr:1234/device.xml")
        service = device.service("urn:schemas-upnp-org:service:RenderingControl:1")
        action = service.action("SetVolume")

        # all ok
        action.validate_arguments(InstanceID=0, Channel="Master", DesiredVolume=10)

        # invalid type for InstanceID
        try:
            action.validate_arguments(
                InstanceID="0", Channel="Master", DesiredVolume=10
            )
            assert False
        except UpnpValueError:
            pass

        # missing DesiredVolume
        try:
            action.validate_arguments(InstanceID="0", Channel="Master")
            assert False
        except UpnpValueError:
            pass

    @pytest.mark.asyncio
    async def test_format_request(self) -> None:
        """Test the request an action sends."""
        requester = UpnpTestRequester(RESPONSE_MAP)
        factory = UpnpFactory(requester)
        device = await factory.async_create_device("http://dlna_dmr:1234/device.xml")
        service = device.service("urn:schemas-upnp-org:service:RenderingControl:1")
        action = service.action("SetVolume")

        service_type = "urn:schemas-upnp-org:service:RenderingControl:1"
        request = action.create_request(
            InstanceID=0, Channel="Master", DesiredVolume=10
        )

        root = DET.fromstring(request.body)
        namespace = {"rc_service": service_type}
        assert root.find(".//rc_service:SetVolume", namespace) is not None
        assert root.find(".//DesiredVolume", namespace) is not None

    @pytest.mark.asyncio
    async def test_format_request_escape(self) -> None:
        """Test escaping the request an action sends."""
        requester = UpnpTestRequester(RESPONSE_MAP)
        factory = UpnpFactory(requester)
        device = await factory.async_create_device("http://dlna_dmr:1234/device.xml")
        service = device.service("urn:schemas-upnp-org:service:AVTransport:1")
        action = service.action("SetAVTransportURI")

        service_type = "urn:schemas-upnp-org:service:AVTransport:1"
        metadata = "<item>test thing</item>"
        request = action.create_request(
            InstanceID=0,
            CurrentURI="http://example.org/file.mp3",
            CurrentURIMetaData=metadata,
        )

        root = DET.fromstring(request.body)
        namespace = {"avt_service": service_type}
        assert root.find(".//avt_service:SetAVTransportURI", namespace) is not None
        assert root.find(".//CurrentURIMetaData", namespace) is not None
        assert (
            root.findtext(".//CurrentURIMetaData", None, namespace)
            == "<item>test thing</item>"
        )

        current_uri_metadata_el = root.find(".//CurrentURIMetaData", namespace)
        assert current_uri_metadata_el is not None
        # This shouldn't have any children, due to its contents being escaped.
        assert current_uri_metadata_el.findall("./") == []

    @pytest.mark.asyncio
    async def test_parse_response(self) -> None:
        """Test calling an action and handling its response."""
        requester = UpnpTestRequester(RESPONSE_MAP)
        factory = UpnpFactory(requester)
        device = await factory.async_create_device("http://dlna_dmr:1234/device.xml")
        service = device.service("urn:schemas-upnp-org:service:RenderingControl:1")
        action = service.action("GetVolume")

        service_type = "urn:schemas-upnp-org:service:RenderingControl:1"
        response_body = read_file("dlna/dmr/action_GetVolume.xml")
        response = HttpResponse(200, {}, response_body)
        result = action.parse_response(service_type, response)
        assert result == {"CurrentVolume": 3}

    @pytest.mark.asyncio
    async def test_parse_response_empty(self) -> None:
        """Test calling an action and handling an empty XML response."""
        requester = UpnpTestRequester(RESPONSE_MAP)
        factory = UpnpFactory(requester)
        device = await factory.async_create_device("http://dlna_dmr:1234/device.xml")
        service = device.service("urn:schemas-upnp-org:service:RenderingControl:1")
        action = service.action("SetVolume")

        service_type = "urn:schemas-upnp-org:service:RenderingControl:1"
        response_body = read_file("dlna/dmr/action_SetVolume.xml")
        response = HttpResponse(200, {}, response_body)
        result = action.parse_response(service_type, response)
        assert result == {}

    @pytest.mark.asyncio
    async def test_parse_response_error(self) -> None:
        """Test calling and action and handling an invalid XML response."""
        requester = UpnpTestRequester(RESPONSE_MAP)
        factory = UpnpFactory(requester)
        device = await factory.async_create_device("http://dlna_dmr:1234/device.xml")
        service = device.service("urn:schemas-upnp-org:service:RenderingControl:1")
        action = service.action("GetVolume")

        service_type = "urn:schemas-upnp-org:service:RenderingControl:1"
        response_body = read_file("dlna/dmr/action_GetVolumeError.xml")
        response = HttpResponse(200, {}, response_body)
        with pytest.raises(UpnpActionError) as exc:
            action.parse_response(service_type, response)
        assert exc.value.error_code == UpnpActionErrorCode.INVALID_ARGS
        assert exc.value.error_desc == "Invalid Args"

    @pytest.mark.asyncio
    async def test_parse_response_escape(self) -> None:
        """Test calling an action and properly (not) escaping the response."""
        requester = UpnpTestRequester(RESPONSE_MAP)
        factory = UpnpFactory(requester)
        device = await factory.async_create_device("http://dlna_dmr:1234/device.xml")
        service = device.service("urn:schemas-upnp-org:service:AVTransport:1")
        action = service.action("GetMediaInfo")

        service_type = "urn:schemas-upnp-org:service:AVTransport:1"
        response_body = read_file("dlna/dmr/action_GetMediaInfo.xml")
        response = HttpResponse(200, {}, response_body)
        result = action.parse_response(service_type, response)
        assert result == {
            "CurrentURI": "uri://1.mp3",
            "CurrentURIMetaData": "<DIDL-Lite "
            'xmlns="urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/" '
            'xmlns:dc="http://purl.org/dc/elements/1.1/" '
            'xmlns:dlna="urn:schemas-dlna-org:metadata-1-0/" '
            'xmlns:sec="http://www.sec.co.kr/" '
            'xmlns:upnp="urn:schemas-upnp-org:metadata-1-0/upnp/" '
            'xmlns:xbmc="urn:schemas-xbmc-org:metadata-1-0/">'
            '<item id="" parentID="" refID="" restricted="1">'
            "<upnp:artist>A &amp; B &gt; C</upnp:artist>"
            "</item>"
            "</DIDL-Lite>",
            "MediaDuration": "00:00:01",
            "NextURI": "",
            "NextURIMetaData": "",
            "NrTracks": 1,
            "PlayMedium": "NONE",
            "RecordMedium": "NOT_IMPLEMENTED",
            "WriteStatus": "NOT_IMPLEMENTED",
        }

    @pytest.mark.asyncio
    async def test_parse_response_no_service_type_version(self) -> None:
        """Test calling and action and handling a response without service type number."""
        requester = UpnpTestRequester(RESPONSE_MAP)
        factory = UpnpFactory(requester)
        device = await factory.async_create_device("http://dlna_dmr:1234/device.xml")
        service = device.service("urn:schemas-upnp-org:service:RenderingControl:1")
        action = service.action("GetVolume")

        service_type = "urn:schemas-upnp-org:service:RenderingControl:1"
        response_body = read_file("dlna/dmr/action_GetVolumeInvalidServiceType.xml")
        response = HttpResponse(200, {}, response_body)
        try:
            action.parse_response(service_type, response)
            assert False
        except UpnpError:
            pass

    @pytest.mark.asyncio
    async def test_parse_response_no_service_type_version_2(self) -> None:
        """Test calling and action and handling a response without service type number."""
        requester = UpnpTestRequester(RESPONSE_MAP)
        factory = UpnpFactory(requester)
        device = await factory.async_create_device("http://dlna_dmr:1234/device.xml")
        service = device.service("urn:schemas-upnp-org:service:AVTransport:1")
        action = service.action("GetTransportInfo")

        service_type = "urn:schemas-upnp-org:service:AVTransport:1"
        response_body = read_file(
            "dlna/dmr/action_GetTransportInfoInvalidServiceType.xml"
        )
        response = HttpResponse(200, {}, response_body)
        try:
            action.parse_response(service_type, response)
            assert False
        except UpnpError:
            pass

    @pytest.mark.asyncio
    async def test_unknown_out_argument(self) -> None:
        """Test calling an action and handling an unknown out-argument."""
        requester = UpnpTestRequester(RESPONSE_MAP)
        device_url = "http://dlna_dmr:1234/device.xml"
        service_type = "urn:schemas-upnp-org:service:RenderingControl:1"
        test_action = "GetVolume"

        factory = UpnpFactory(requester)
        device = await factory.async_create_device(device_url)
        service = device.service(service_type)
        action = service.action(test_action)

        response_body = read_file("dlna/dmr/action_GetVolumeExtraOutParameter.xml")
        response = HttpResponse(200, {}, response_body)
        try:
            action.parse_response(service_type, response)
            assert False
        except UpnpError:
            pass

        factory = UpnpFactory(requester, non_strict=True)
        device = await factory.async_create_device(device_url)
        service = device.service(service_type)
        action = service.action(test_action)

        try:
            action.parse_response(service_type, response)
        except UpnpError:
            assert False

    @pytest.mark.asyncio
    async def test_response_invalid_xml_namespaces(self) -> None:
        """Test parsing response with invalid XML namespaces."""
        requester = UpnpTestRequester(RESPONSE_MAP)
        device_url = "http://igd:1234/device.xml"
        service_type = "urn:schemas-upnp-org:service:WANIPConnection:1"
        test_action = "DeletePortMapping"

        # Test strict mode.
        factory = UpnpFactory(requester)
        device = await factory.async_create_device(device_url)
        service = device.find_service(service_type)
        assert service is not None
        action = service.action(test_action)

        response_body = read_file("igd/action_WANPIPConnection_DeletePortMapping.xml")
        response = HttpResponse(200, {}, response_body)
        try:
            action.parse_response(service_type, response)
            assert False
        except UpnpError:
            pass

        # Test non-strict mode.
        factory = UpnpFactory(requester, non_strict=True)
        device = await factory.async_create_device(device_url)
        service = device.find_service(service_type)
        assert service is not None
        action = service.action(test_action)

        try:
            action.parse_response(service_type, response)
        except UpnpError:
            assert False


class TestUpnpService:
    """Tests for UpnpService."""

    @pytest.mark.asyncio
    async def test_init(self) -> None:
        """Test initializing a UpnpService."""
        requester = UpnpTestRequester(RESPONSE_MAP)
        factory = UpnpFactory(requester)
        device = await factory.async_create_device("http://dlna_dmr:1234/device.xml")
        service = device.service("urn:schemas-upnp-org:service:RenderingControl:1")

        base_url = "http://dlna_dmr:1234"
        assert service
        assert service.service_type == "urn:schemas-upnp-org:service:RenderingControl:1"
        assert service.control_url == base_url + "/upnp/control/RenderingControl1"
        assert service.event_sub_url == base_url + "/upnp/event/RenderingControl1"
        assert service.scpd_url == base_url + "/RenderingControl_1.xml"

    @pytest.mark.asyncio
    async def test_state_variables_actions(self) -> None:
        """Test eding a UpnpStateVariable."""
        requester = UpnpTestRequester(RESPONSE_MAP)
        factory = UpnpFactory(requester)
        device = await factory.async_create_device("http://dlna_dmr:1234/device.xml")
        service = device.service("urn:schemas-upnp-org:service:RenderingControl:1")

        state_var = service.state_variable("Volume")
        assert state_var

        action = service.action("GetVolume")
        assert action

    @pytest.mark.asyncio
    async def test_call_action(self) -> None:
        """Test calling a UpnpAction."""
        responses: MutableMapping = {
            (
                "POST",
                "http://dlna_dmr:1234/upnp/control/RenderingControl1",
            ): HttpResponse(
                200,
                {},
                read_file("dlna/dmr/action_GetVolume.xml"),
            )
        }
        responses.update(RESPONSE_MAP)
        requester = UpnpTestRequester(responses)
        factory = UpnpFactory(requester)
        device = await factory.async_create_device("http://dlna_dmr:1234/device.xml")
        service = device.service("urn:schemas-upnp-org:service:RenderingControl:1")
        action = service.action("GetVolume")

        result = await service.async_call_action(action, InstanceID=0, Channel="Master")
        assert result["CurrentVolume"] == 3

    @pytest.mark.asyncio
    async def test_soap_fault_http_error(self) -> None:
        """Test an action response with HTTP error and SOAP fault raises exception."""
        responses: MutableMapping = {
            (
                "POST",
                "http://dlna_dmr:1234/upnp/control/RenderingControl1",
            ): HttpResponse(
                500,
                {},
                read_file("dlna/dmr/action_GetVolumeError.xml"),
            )
        }
        responses.update(RESPONSE_MAP)
        requester = UpnpTestRequester(responses)
        factory = UpnpFactory(requester)
        device = await factory.async_create_device("http://dlna_dmr:1234/device.xml")
        service = device.service("urn:schemas-upnp-org:service:RenderingControl:1")
        action = service.action("GetVolume")

        with pytest.raises(UpnpActionResponseError) as exc:
            await service.async_call_action(action, InstanceID=0, Channel="Master")
        assert exc.value.error_code == UpnpActionErrorCode.INVALID_ARGS
        assert exc.value.error_desc == "Invalid Args"
        assert exc.value.status == 500

    @pytest.mark.asyncio
    async def test_http_error(self) -> None:
        """Test an action response with HTTP error and blank body raises exception."""
        responses: MutableMapping = {
            (
                "POST",
                "http://dlna_dmr:1234/upnp/control/RenderingControl1",
            ): HttpResponse(
                500,
                {},
                "",
            )
        }
        responses.update(RESPONSE_MAP)
        requester = UpnpTestRequester(responses)
        factory = UpnpFactory(requester)
        device = await factory.async_create_device("http://dlna_dmr:1234/device.xml")
        service = device.service("urn:schemas-upnp-org:service:RenderingControl:1")
        action = service.action("GetVolume")

        with pytest.raises(UpnpResponseError) as exc:
            await service.async_call_action(action, InstanceID=0, Channel="Master")
        assert exc.value.status == 500

    @pytest.mark.asyncio
    async def test_soap_fault_http_ok(self) -> None:
        """Test an action response with HTTP OK but SOAP fault raises exception."""
        responses: MutableMapping = {
            (
                "POST",
                "http://dlna_dmr:1234/upnp/control/RenderingControl1",
            ): HttpResponse(
                200,
                {},
                read_file("dlna/dmr/action_GetVolumeError.xml"),
            )
        }
        responses.update(RESPONSE_MAP)
        requester = UpnpTestRequester(responses)
        factory = UpnpFactory(requester)
        device = await factory.async_create_device("http://dlna_dmr:1234/device.xml")
        service = device.service("urn:schemas-upnp-org:service:RenderingControl:1")
        action = service.action("GetVolume")

        with pytest.raises(UpnpActionError) as exc:
            await service.async_call_action(action, InstanceID=0, Channel="Master")
        assert exc.value.error_code == UpnpActionErrorCode.INVALID_ARGS
        assert exc.value.error_desc == "Invalid Args"

    @pytest.mark.parametrize(
        "rc_doc",
        [
            "dlna/dmr/RenderingControl_1_bad_namespace.xml",  # Bad namespace
            "dlna/dmr/RenderingControl_1_bad_root_tag.xml",  # Wrong root tag
            "dlna/dmr/RenderingControl_1_missing_state_table.xml",  # Missing state table
        ],
    )
    @pytest.mark.asyncio
    async def test_bad_scpd_strict(self, rc_doc: str) -> None:
        """Test handling of bad service descriptions in strict mode."""
        responses = dict(RESPONSE_MAP)
        responses[("GET", "http://dlna_dmr:1234/RenderingControl_1.xml")] = (
            HttpResponse(
                200,
                {},
                read_file(rc_doc),
            )
        )
        requester = UpnpTestRequester(responses)
        factory = UpnpFactory(requester)
        with pytest.raises(UpnpXmlContentError):
            await factory.async_create_device("http://dlna_dmr:1234/device.xml")

    @pytest.mark.parametrize(
        "rc_doc",
        [
            "dlna/dmr/RenderingControl_1_bad_namespace.xml",  # Bad namespace
            "dlna/dmr/RenderingControl_1_bad_root_tag.xml",  # Wrong root tag
            "dlna/dmr/RenderingControl_1_missing_state_table.xml",  # Missing state table
        ],
    )
    @pytest.mark.asyncio
    async def test_bad_scpd_non_strict_fails(self, rc_doc: str) -> None:
        """Test bad SCPD in non-strict mode."""
        responses = dict(RESPONSE_MAP)
        responses[("GET", "http://dlna_dmr:1234/RenderingControl_1.xml")] = (
            HttpResponse(
                200,
                {},
                read_file(rc_doc),
            )
        )
        requester = UpnpTestRequester(responses)
        factory = UpnpFactory(requester, non_strict=True)
        device = await factory.async_create_device("http://dlna_dmr:1234/device.xml")
        # Known good service
        assert device.services["urn:schemas-upnp-org:service:AVTransport:1"]
        # Bad service will also exist, to some extent
        assert device.services["urn:schemas-upnp-org:service:RenderingControl:1"]
