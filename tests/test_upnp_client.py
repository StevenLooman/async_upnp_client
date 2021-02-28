# -*- coding: utf-8 -*-
"""Unit tests for upnp_client."""

from datetime import datetime

from typing import List, Mapping

import defusedxml.ElementTree as ET
import pytest  # type: ignore

from async_upnp_client import (
    UpnpError,
    UpnpEventHandler,
    UpnpFactory,
    UpnpStateVariable,
    UpnpValueError,
)

from .upnp_test_requester import read_file
from .upnp_test_requester import UpnpTestRequester
from .upnp_test_requester import RESPONSE_MAP


class TestUpnpStateVariable:

    @pytest.mark.asyncio
    async def test_init(self):
        requester = UpnpTestRequester(RESPONSE_MAP)
        factory = UpnpFactory(requester)
        device = await factory.async_create_device('http://localhost:1234/dmr')
        assert device

        service = device.service('urn:schemas-upnp-org:service:RenderingControl:1')
        assert service

        state_var = service.state_variable('Volume')
        assert state_var

        action = service.action('GetVolume')
        assert action

        argument = action.argument('InstanceID')
        assert argument

    @pytest.mark.asyncio
    async def test_init_xml(self):
        requester = UpnpTestRequester(RESPONSE_MAP)
        factory = UpnpFactory(requester)
        device = await factory.async_create_device('http://localhost:1234/dmr')
        assert device.xml is not None

        service = device.service('urn:schemas-upnp-org:service:RenderingControl:1')
        assert service.xml is not None

        state_var = service.state_variable('Volume')
        assert state_var.xml is not None

        action = service.action('GetVolume')
        assert action.xml is not None

        argument = action.argument('InstanceID')
        assert argument.xml is not None

    @pytest.mark.asyncio
    async def test_set_value_volume(self):
        requester = UpnpTestRequester(RESPONSE_MAP)
        factory = UpnpFactory(requester)
        device = await factory.async_create_device('http://localhost:1234/dmr')
        service = device.service('urn:schemas-upnp-org:service:RenderingControl:1')
        state_var = service.state_variable('Volume')

        state_var.value = 10
        assert state_var.value == 10
        assert state_var.upnp_value == '10'

        state_var.upnp_value = '20'
        assert state_var.value == 20
        assert state_var.upnp_value == '20'

    @pytest.mark.asyncio
    async def test_set_value_mute(self):
        requester = UpnpTestRequester(RESPONSE_MAP)
        factory = UpnpFactory(requester)
        device = await factory.async_create_device('http://localhost:1234/dmr')
        service = device.service('urn:schemas-upnp-org:service:RenderingControl:1')
        state_var = service.state_variable('Mute')

        state_var.value = True
        assert state_var.value is True
        assert state_var.upnp_value == '1'

        state_var.value = False
        assert state_var.value is False
        assert state_var.upnp_value == '0'

        state_var.upnp_value = '1'
        assert state_var.value is True
        assert state_var.upnp_value == '1'

        state_var.upnp_value = '0'
        assert state_var.value is False
        assert state_var.upnp_value == '0'

    @pytest.mark.asyncio
    async def test_value_min_max(self):
        requester = UpnpTestRequester(RESPONSE_MAP)
        factory = UpnpFactory(requester)
        device = await factory.async_create_device('http://localhost:1234/dmr')
        service = device.service('urn:schemas-upnp-org:service:RenderingControl:1')
        state_var = service.state_variable('Volume')

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
    async def test_value_min_max_validation_disable(self):
        requester = UpnpTestRequester(RESPONSE_MAP)
        factory = UpnpFactory(requester, disable_state_variable_validation=True)
        device = await factory.async_create_device('http://localhost:1234/dmr')
        service = device.service('urn:schemas-upnp-org:service:RenderingControl:1')
        state_var = service.state_variable('Volume')

        # min/max are set
        assert state_var.min_value == 0
        assert state_var.max_value == 100

        # min/max are not validated
        state_var.value = -10
        assert state_var.value == -10

        state_var.value = 110
        assert state_var.value == 110

    @pytest.mark.asyncio
    async def test_value_allowed_value(self):
        requester = UpnpTestRequester(RESPONSE_MAP)
        factory = UpnpFactory(requester)
        device = await factory.async_create_device('http://localhost:1234/dmr')
        service = device.service('urn:schemas-upnp-org:service:RenderingControl:1')
        state_var = service.state_variable('A_ARG_TYPE_Channel')

        assert state_var.allowed_values == ['Master']

        # should be ok
        state_var.value = 'Master'
        assert state_var.value == 'Master'

        try:
            state_var.value = 'Left'
            assert False
        except UpnpValueError:
            pass

    @pytest.mark.asyncio
    async def test_value_upnp_value_error(self):
        requester = UpnpTestRequester(RESPONSE_MAP)
        factory = UpnpFactory(requester, disable_state_variable_validation=True)
        device = await factory.async_create_device('http://localhost:1234/dmr')
        service = device.service('urn:schemas-upnp-org:service:RenderingControl:1')
        state_var = service.state_variable('Volume')

        # should be ok
        state_var.upnp_value = '50'
        assert state_var.value == 50

        # should set UpnpStateVariable.UPNP_VALUE_ERROR
        state_var.upnp_value = 'abc'
        assert state_var.value is None
        assert state_var.value_unchecked is UpnpStateVariable.UPNP_VALUE_ERROR

    @pytest.mark.asyncio
    async def test_value_date_time(self):
        requester = UpnpTestRequester(RESPONSE_MAP)
        factory = UpnpFactory(requester, disable_state_variable_validation=True)
        device = await factory.async_create_device('http://localhost:1234/dmr')
        service = device.service('urn:schemas-upnp-org:service:RenderingControl:1')
        state_var = service.state_variable('SV1')

        # should be ok
        state_var.upnp_value = '1985-04-12T10:15:30'
        assert state_var.value == datetime(1985, 4, 12, 10, 15, 30)

    @pytest.mark.asyncio
    async def test_value_date_time_tz(self):
        requester = UpnpTestRequester(RESPONSE_MAP)
        factory = UpnpFactory(requester, disable_state_variable_validation=True)
        device = await factory.async_create_device('http://localhost:1234/dmr')
        service = device.service('urn:schemas-upnp-org:service:RenderingControl:1')
        state_var = service.state_variable('SV2')

        # should be ok
        state_var.upnp_value = '1985-04-12T10:15:30+0400'
        assert state_var.value == datetime(1985, 4, 12, 10, 15, 30, tzinfo=state_var.value.tzinfo)
        assert state_var.value.tzinfo is not None

    @pytest.mark.asyncio
    async def test_send_events(self):
        requester = UpnpTestRequester(RESPONSE_MAP)
        factory = UpnpFactory(requester)
        device = await factory.async_create_device('http://localhost:1234/dmr')
        service = device.service('urn:schemas-upnp-org:service:RenderingControl:1')

        state_var = service.state_variable('A_ARG_TYPE_InstanceID')  # old style
        assert state_var.send_events is False

        state_var = service.state_variable('A_ARG_TYPE_Channel')  # new style
        assert state_var.send_events is False

        state_var = service.state_variable('Volume')  # broken/none given
        assert state_var.send_events is False

        state_var = service.state_variable('LastChange')
        assert state_var.send_events is True


class TestUpnpServiceAction:

    @pytest.mark.asyncio
    async def test_init(self):
        requester = UpnpTestRequester(RESPONSE_MAP)
        factory = UpnpFactory(requester)
        device = await factory.async_create_device('http://localhost:1234/dmr')
        service = device.service('urn:schemas-upnp-org:service:RenderingControl:1')
        action = service.action('GetVolume')

        assert action
        assert action.name == 'GetVolume'

    @pytest.mark.asyncio
    async def test_valid_arguments(self):
        requester = UpnpTestRequester(RESPONSE_MAP)
        factory = UpnpFactory(requester)
        device = await factory.async_create_device('http://localhost:1234/dmr')
        service = device.service('urn:schemas-upnp-org:service:RenderingControl:1')
        action = service.action('SetVolume')

        # all ok
        action.validate_arguments(InstanceID=0, Channel='Master', DesiredVolume=10)

        # invalid type for InstanceID
        try:
            action.validate_arguments(InstanceID='0', Channel='Master', DesiredVolume=10)
            assert False
        except UpnpValueError:
            pass

        # missing DesiredVolume
        try:
            action.validate_arguments(InstanceID='0', Channel='Master')
            assert False
        except UpnpValueError:
            pass

    @pytest.mark.asyncio
    async def test_format_request(self):
        requester = UpnpTestRequester(RESPONSE_MAP)
        factory = UpnpFactory(requester)
        device = await factory.async_create_device('http://localhost:1234/dmr')
        service = device.service('urn:schemas-upnp-org:service:RenderingControl:1')
        action = service.action('SetVolume')

        service_type = 'urn:schemas-upnp-org:service:RenderingControl:1'
        _, _, body = action.create_request(InstanceID=0, Channel='Master', DesiredVolume=10)

        root = ET.fromstring(body)
        namespace = {'rc_service': service_type}
        assert root.find('.//rc_service:SetVolume', namespace) is not None
        assert root.find('.//DesiredVolume', namespace) is not None

    @pytest.mark.asyncio
    async def test_format_request_escape(self):
        requester = UpnpTestRequester(RESPONSE_MAP)
        factory = UpnpFactory(requester)
        device = await factory.async_create_device('http://localhost:1234/dmr')
        service = device.service('urn:schemas-upnp-org:service:AVTransport:1')
        action = service.action('SetAVTransportURI')

        service_type = 'urn:schemas-upnp-org:service:AVTransport:1'
        metadata = '<item>test thing</item>'
        _, _, body = action.create_request(
            InstanceID=0,
            CurrentURI='http://example.org/file.mp3',
            CurrentURIMetaData=metadata)

        root = ET.fromstring(body)
        namespace = {'avt_service': service_type}
        assert root.find('.//avt_service:SetAVTransportURI', namespace) is not None
        assert root.find('.//CurrentURIMetaData', namespace) is not None
        assert root.findtext('.//CurrentURIMetaData', None, namespace) == '<item>test thing</item>'

        current_uri_metadata_el = root.find('.//CurrentURIMetaData', namespace)
        assert current_uri_metadata_el is not None
        # This shouldn't have any children, due to its contents being escaped.
        assert current_uri_metadata_el.findall('./') == []

    @pytest.mark.asyncio
    async def test_parse_response(self):
        requester = UpnpTestRequester(RESPONSE_MAP)
        factory = UpnpFactory(requester)
        device = await factory.async_create_device('http://localhost:1234/dmr')
        service = device.service('urn:schemas-upnp-org:service:RenderingControl:1')
        action = service.action('GetVolume')

        service_type = 'urn:schemas-upnp-org:service:RenderingControl:1'
        response = read_file('action_GetVolume.xml')
        result = action.parse_response(service_type, {}, response)
        assert result == {'CurrentVolume': 3}

    @pytest.mark.asyncio
    async def test_parse_response_empty(self):
        requester = UpnpTestRequester(RESPONSE_MAP)
        factory = UpnpFactory(requester)
        device = await factory.async_create_device('http://localhost:1234/dmr')
        service = device.service('urn:schemas-upnp-org:service:RenderingControl:1')
        action = service.action('SetVolume')

        service_type = 'urn:schemas-upnp-org:service:RenderingControl:1'
        response = read_file('action_SetVolume.xml')
        result = action.parse_response(service_type, {}, response)
        assert result == {}

    @pytest.mark.asyncio
    async def test_parse_response_error(self):
        requester = UpnpTestRequester(RESPONSE_MAP)
        factory = UpnpFactory(requester)
        device = await factory.async_create_device('http://localhost:1234/dmr')
        service = device.service('urn:schemas-upnp-org:service:RenderingControl:1')
        action = service.action('GetVolume')

        service_type = 'urn:schemas-upnp-org:service:RenderingControl:1'
        response = read_file('action_GetVolumeError.xml')
        try:
            action.parse_response(service_type, {}, response)
            assert False
        except UpnpError:
            pass

    @pytest.mark.asyncio
    async def test_unknown_out_argument(self):
        requester = UpnpTestRequester(RESPONSE_MAP)
        link_service = 'http://localhost:1234/dmr'
        service_type = 'urn:schemas-upnp-org:service:RenderingControl:1'
        test_action = 'GetVolume'

        factory = UpnpFactory(requester)
        device = await factory.async_create_device(link_service)
        service = device.service(service_type)
        action = service.action(test_action)

        response = read_file('action_GetVolumeExtraOutParameter.xml')
        try:
            action.parse_response(service_type, {}, response)
            assert False
        except UpnpError:
            pass

        factory = UpnpFactory(requester,disable_unknown_out_argument_error=True)
        device = await factory.async_create_device(link_service)
        service = device.service(service_type)
        action = service.action(test_action)

        try:
            action.parse_response(service_type, {}, response)
        except UpnpError:
            assert False


class TestUpnpService:

    @pytest.mark.asyncio
    async def test_init(self):
        requester = UpnpTestRequester(RESPONSE_MAP)
        factory = UpnpFactory(requester)
        device = await factory.async_create_device('http://localhost:1234/dmr')
        service = device.service('urn:schemas-upnp-org:service:RenderingControl:1')

        base_url = 'http://localhost:1234'
        assert service
        assert service.service_type == 'urn:schemas-upnp-org:service:RenderingControl:1'
        assert service.control_url == base_url + '/upnp/control/RenderingControl1'
        assert service.event_sub_url == base_url + '/upnp/event/RenderingControl1'
        assert service.scpd_url == base_url + '/RenderingControl_1.xml'

    @pytest.mark.asyncio
    async def test_state_variables_actions(self):
        requester = UpnpTestRequester(RESPONSE_MAP)
        factory = UpnpFactory(requester)
        device = await factory.async_create_device('http://localhost:1234/dmr')
        service = device.service('urn:schemas-upnp-org:service:RenderingControl:1')

        state_var = service.state_variable('Volume')
        assert state_var

        action = service.action('GetVolume')
        assert action

    @pytest.mark.asyncio
    async def test_call_action(self):
        responses: Mapping = {
            ('POST', 'http://localhost:1234/upnp/control/RenderingControl1'):
                (200, {}, read_file('action_GetVolume.xml'))
        }
        responses.update(RESPONSE_MAP)
        requester = UpnpTestRequester(responses)
        factory = UpnpFactory(requester)
        device = await factory.async_create_device('http://localhost:1234/dmr')
        service = device.service('urn:schemas-upnp-org:service:RenderingControl:1')
        action = service.action('GetVolume')

        result = await service.async_call_action(action, InstanceID=0, Channel='Master')
        assert result['CurrentVolume'] == 3


class TestUpnpEventHandler:

    @pytest.mark.asyncio
    async def test_subscribe(self):
        requester = UpnpTestRequester(RESPONSE_MAP)
        factory = UpnpFactory(requester)
        device = await factory.async_create_device('http://localhost:1234/dmr')
        event_handler = UpnpEventHandler('http://localhost:11302', requester)

        service = device.service('urn:schemas-upnp-org:service:RenderingControl:1')
        success, sid = await event_handler.async_subscribe(service)
        assert event_handler.service_for_sid('uuid:dummy') == service
        assert success is True
        assert sid == 'uuid:dummy'

    @pytest.mark.asyncio
    async def test_subscribe_renew(self):
        requester = UpnpTestRequester(RESPONSE_MAP)
        factory = UpnpFactory(requester)
        device = await factory.async_create_device('http://localhost:1234/dmr')
        event_handler = UpnpEventHandler('http://localhost:11302', requester)

        service = device.service('urn:schemas-upnp-org:service:RenderingControl:1')
        success, sid = await event_handler.async_subscribe(service)
        assert success is True
        assert sid == 'uuid:dummy'
        assert event_handler.service_for_sid('uuid:dummy') == service

        success, sid = await event_handler.async_resubscribe(service)
        assert event_handler.service_for_sid('uuid:dummy') == service
        assert success is True
        assert sid == 'uuid:dummy'

    @pytest.mark.asyncio
    async def test_unsubscribe(self):
        requester = UpnpTestRequester(RESPONSE_MAP)
        factory = UpnpFactory(requester)
        device = await factory.async_create_device('http://localhost:1234/dmr')
        event_handler = UpnpEventHandler('http://localhost:11302', requester)

        service = device.service('urn:schemas-upnp-org:service:RenderingControl:1')
        success, sid = await event_handler.async_subscribe(service)
        assert event_handler.service_for_sid('uuid:dummy') == service
        assert success is True
        assert sid == 'uuid:dummy'

        success, old_sid = await event_handler.async_unsubscribe(service)
        assert event_handler.service_for_sid('uuid:dummy') is None
        assert success is True
        assert old_sid == 'uuid:dummy'

    @pytest.mark.asyncio
    async def test_on_notify_upnp_event(self):
        changed_vars: List[UpnpStateVariable] = []

        def on_event(self, changed_state_variables):
            # pylint: disable=unused-argument
            nonlocal changed_vars
            changed_vars = changed_state_variables

        requester = UpnpTestRequester(RESPONSE_MAP)
        factory = UpnpFactory(requester)
        device = await factory.async_create_device('http://localhost:1234/dmr')
        service = device.service('urn:schemas-upnp-org:service:RenderingControl:1')
        service.on_event = on_event
        event_handler = UpnpEventHandler('http://localhost:11302', requester)
        await event_handler.async_subscribe(service)

        headers = {
            'NT': 'upnp:event',
            'NTS': 'upnp:propchange',
            'SID': 'uuid:dummy',
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

        state_var = service.state_variable('Volume')
        assert state_var.value == 60
