"""Unit tests for upnp_client."""

import asyncio
import os.path
from copy import copy

import pytest
import xml.etree.ElementTree as ET

from async_upnp_client import (
    UpnpError,
    UpnpEventHandler,
    UpnpFactory,
    UpnpRequester,
    UpnpStateVariable,
    UpnpValueError,
)
from async_upnp_client.dlna import dlna_handle_notify_last_change


NS = {
    'device': 'urn:schemas-upnp-org:device-1-0',
    'service': 'urn:schemas-upnp-org:service-1-0',
}


def read_file(filename):
    path = os.path.join('tests', 'fixtures', filename)
    with open(path, 'r') as f:
        return f.read()


class UpnpTestRequester(UpnpRequester):

    def __init__(self, response_map):
        self._response_map = copy(response_map)
        self._received_requests = {}

    async def async_do_http_request(self, method, url, headers=None, body=None, body_type='text'):
        await asyncio.sleep(0.01)

        key = (method, url)
        if key not in self._response_map:
            raise Exception('Request not in response map')

        self._received_requests[key] = (headers, body)

        return self._response_map[key]

    def headers(self, method, url):
        key = (method, url)
        return self._received_requests[key]


RESPONSE_MAP = {
    ('GET', 'http://localhost:1234/dmr'):
        (200, {}, read_file('dmr')),
    ('GET', 'http://localhost:1234/RenderingControl_1.xml'):
        (200, {}, read_file('RenderingControl_1.xml')),
    ('GET', 'http://localhost:1234/AVTransport_1.xml'):
        (200, {}, read_file('AVTransport_1.xml')),
    ('SUBSCRIBE', 'http://localhost:1234/upnp/event/RenderingControl1'):
        (200, {'sid': 'uuid:dummy'}, ''),
    ('UNSUBSCRIBE', 'http://localhost:1234/upnp/event/RenderingControl1'):
        (200, {'sid': 'uuid:dummy'}, ''),
}


class TestUpnpStateVariable:

    @pytest.mark.asyncio
    async def test_init(self):
        r = UpnpTestRequester(RESPONSE_MAP)
        factory = UpnpFactory(r)
        device = await factory.async_create_device('http://localhost:1234/dmr')
        assert device

        service = device.service('urn:schemas-upnp-org:service:RenderingControl:1')
        assert service

        state_var = service.state_variable('Volume')
        assert state_var

    @pytest.mark.asyncio
    async def test_set_value_volume(self):
        r = UpnpTestRequester(RESPONSE_MAP)
        factory = UpnpFactory(r)
        device = await factory.async_create_device('http://localhost:1234/dmr')
        service = device.service('urn:schemas-upnp-org:service:RenderingControl:1')
        sv = service.state_variable('Volume')

        sv.value = 10
        assert sv.value == 10
        assert sv.upnp_value == '10'

        sv.upnp_value = '20'
        assert sv.value == 20
        assert sv.upnp_value == '20'

    @pytest.mark.asyncio
    async def test_set_value_mute(self):
        r = UpnpTestRequester(RESPONSE_MAP)
        factory = UpnpFactory(r)
        device = await factory.async_create_device('http://localhost:1234/dmr')
        service = device.service('urn:schemas-upnp-org:service:RenderingControl:1')
        sv = service.state_variable('Mute')

        sv.value = True
        assert sv.value is True
        assert sv.upnp_value == '1'

        sv.value = False
        assert sv.value is False
        assert sv.upnp_value == '0'

        sv.upnp_value = '1'
        assert sv.value is True
        assert sv.upnp_value == '1'

        sv.upnp_value = '0'
        assert sv.value is False
        assert sv.upnp_value == '0'

    @pytest.mark.asyncio
    async def test_value_min_max(self):
        r = UpnpTestRequester(RESPONSE_MAP)
        factory = UpnpFactory(r)
        device = await factory.async_create_device('http://localhost:1234/dmr')
        service = device.service('urn:schemas-upnp-org:service:RenderingControl:1')
        sv = service.state_variable('Volume')

        assert sv.min_value == 0
        assert sv.max_value == 100

        sv.value = 10
        assert sv.value == 10

        try:
            sv.value = -10
            assert False
        except UpnpValueError:
            pass

        try:
            sv.value = 110
            assert False
        except UpnpValueError:
            pass

    @pytest.mark.asyncio
    async def test_value_min_max_validation_disable(self):
        r = UpnpTestRequester(RESPONSE_MAP)
        factory = UpnpFactory(r, disable_state_variable_validation=True)
        device = await factory.async_create_device('http://localhost:1234/dmr')
        service = device.service('urn:schemas-upnp-org:service:RenderingControl:1')
        sv = service.state_variable('Volume')

        # min/max are set
        assert sv.min_value == 0
        assert sv.max_value == 100

        # min/max are not validated
        sv.value = -10
        assert sv.value == -10

        sv.value = 110
        assert sv.value == 110

    @pytest.mark.asyncio
    async def test_value_allowed_value(self):
        r = UpnpTestRequester(RESPONSE_MAP)
        factory = UpnpFactory(r)
        device = await factory.async_create_device('http://localhost:1234/dmr')
        service = device.service('urn:schemas-upnp-org:service:RenderingControl:1')
        sv = service.state_variable('A_ARG_TYPE_Channel')

        assert sv.allowed_values == ['Master']

        # should be ok
        sv.value = 'Master'
        assert sv.value == 'Master'

        try:
            sv.value = 'Left'
            assert False
        except UpnpValueError:
            pass

    @pytest.mark.asyncio
    async def test_value_upnp_value_error(self):
        r = UpnpTestRequester(RESPONSE_MAP)
        factory = UpnpFactory(r, disable_state_variable_validation=True)
        device = await factory.async_create_device('http://localhost:1234/dmr')
        service = device.service('urn:schemas-upnp-org:service:RenderingControl:1')
        sv = service.state_variable('Volume')

        # should be ok
        sv.upnp_value = '50'
        assert sv.value == 50

        # should set UpnpStateVariable.UPNP_VALUE_ERROR
        sv.upnp_value = 'abc'
        assert sv.value is None
        assert sv.value_unchecked is UpnpStateVariable.UPNP_VALUE_ERROR

    @pytest.mark.asyncio
    async def test_send_events(self):
        r = UpnpTestRequester(RESPONSE_MAP)
        factory = UpnpFactory(r)
        device = await factory.async_create_device('http://localhost:1234/dmr')
        service = device.service('urn:schemas-upnp-org:service:RenderingControl:1')

        sv = service.state_variable('A_ARG_TYPE_InstanceID')  # old style
        assert sv.send_events == False

        sv = service.state_variable('A_ARG_TYPE_Channel')  # new style
        assert sv.send_events == False

        sv = service.state_variable('Volume')  # broken/none given
        assert sv.send_events == False

        sv = service.state_variable('LastChange')
        assert sv.send_events == True


class TestUpnpServiceAction:

    @pytest.mark.asyncio
    async def test_init(self):
        r = UpnpTestRequester(RESPONSE_MAP)
        factory = UpnpFactory(r)
        device = await factory.async_create_device('http://localhost:1234/dmr')
        service = device.service('urn:schemas-upnp-org:service:RenderingControl:1')
        action = service.action('GetVolume')

        assert action
        assert action.name == 'GetVolume'

    @pytest.mark.asyncio
    async def test_valid_arguments(self):
        r = UpnpTestRequester(RESPONSE_MAP)
        factory = UpnpFactory(r)
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
        r = UpnpTestRequester(RESPONSE_MAP)
        factory = UpnpFactory(r)
        device = await factory.async_create_device('http://localhost:1234/dmr')
        service = device.service('urn:schemas-upnp-org:service:RenderingControl:1')
        action = service.action('SetVolume')

        service_type = 'urn:schemas-upnp-org:service:RenderingControl:1'
        url, headers, body = action.create_request(InstanceID=0, Channel='Master', DesiredVolume=10)

        root = ET.fromstring(body)
        ns = {'rc_service': service_type}
        assert root.find('.//rc_service:SetVolume', ns) is not None
        assert root.find('.//DesiredVolume', ns) is not None

    @pytest.mark.asyncio
    async def test_format_request_escape(self):
        r = UpnpTestRequester(RESPONSE_MAP)
        factory = UpnpFactory(r)
        device = await factory.async_create_device('http://localhost:1234/dmr')
        service = device.service('urn:schemas-upnp-org:service:AVTransport:1')
        action = service.action('SetAVTransportURI')

        service_type = 'urn:schemas-upnp-org:service:AVTransport:1'
        metadata = '<item>test thing</item>'
        url, headers, body = action.create_request(InstanceID=0, CurrentURI='http://example.org/file.mp3', CurrentURIMetaData=metadata)

        root = ET.fromstring(body)
        ns = {'avt_service': service_type}
        assert root.find('.//avt_service:SetAVTransportURI', ns) is not None
        assert root.find('.//CurrentURIMetaData', ns) is not None
        #assert root.find('.//CurrentURIMetaData', ns).text == '&lt;item&gt;test thing&lt;/item&gt;'
        assert root.find('.//CurrentURIMetaData', ns).text == '<item>test thing</item>'  # ET escapes for us...
        assert root.find('.//CurrentURIMetaData', ns).findall('./') == []  # this shouldn't have any children, due to its contents being escaped

    @pytest.mark.asyncio
    async def test_parse_response(self):
        r = UpnpTestRequester(RESPONSE_MAP)
        factory = UpnpFactory(r)
        device = await factory.async_create_device('http://localhost:1234/dmr')
        service = device.service('urn:schemas-upnp-org:service:RenderingControl:1')
        action = service.action('GetVolume')

        service_type = 'urn:schemas-upnp-org:service:RenderingControl:1'
        response = read_file('action_GetVolume.xml')
        result = action.parse_response(service_type, {}, response)
        assert result == {'CurrentVolume': 3}

    @pytest.mark.asyncio
    async def test_parse_response_error(self):
        r = UpnpTestRequester(RESPONSE_MAP)
        factory = UpnpFactory(r)
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


class TestUpnpService:

    @pytest.mark.asyncio
    async def test_init(self):
        r = UpnpTestRequester(RESPONSE_MAP)
        factory = UpnpFactory(r)
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
        r = UpnpTestRequester(RESPONSE_MAP)
        factory = UpnpFactory(r)
        device = await factory.async_create_device('http://localhost:1234/dmr')
        service = device.service('urn:schemas-upnp-org:service:RenderingControl:1')

        state_var = service.state_variable('Volume')
        assert state_var

        action = service.action('GetVolume')
        assert action

    @pytest.mark.asyncio
    async def test_call_action(self):
        responses = {
            ('POST', 'http://localhost:1234/upnp/control/RenderingControl1'):
                (200, {}, read_file('action_GetVolume.xml'))
        }
        responses.update(RESPONSE_MAP)
        r = UpnpTestRequester(responses)
        factory = UpnpFactory(r)
        device = await factory.async_create_device('http://localhost:1234/dmr')
        service = device.service('urn:schemas-upnp-org:service:RenderingControl:1')
        action = service.action('GetVolume')

        result = await service.async_call_action(action, InstanceID=0, Channel='Master')
        assert result['CurrentVolume'] == 3


class TestUpnpEventHandler:

    @pytest.mark.asyncio
    async def test_subscribe(self):
        r = UpnpTestRequester(RESPONSE_MAP)
        factory = UpnpFactory(r)
        device = await factory.async_create_device('http://localhost:1234/dmr')
        event_handler = UpnpEventHandler('http://localhost:11302', r)

        service = device.service('urn:schemas-upnp-org:service:RenderingControl:1')
        ok, sid = await event_handler.async_subscribe(service)
        assert event_handler.service_for_sid('uuid:dummy') == service
        assert ok is True
        assert sid == 'uuid:dummy'

    @pytest.mark.asyncio
    async def test_subscribe_renew(self):
        r = UpnpTestRequester(RESPONSE_MAP)
        factory = UpnpFactory(r)
        device = await factory.async_create_device('http://localhost:1234/dmr')
        event_handler = UpnpEventHandler('http://localhost:11302', r)

        service = device.service('urn:schemas-upnp-org:service:RenderingControl:1')
        ok, sid = await event_handler.async_subscribe(service)
        assert ok is True
        assert sid == 'uuid:dummy'
        assert event_handler.service_for_sid('uuid:dummy') == service

        ok, sid = await event_handler.async_resubscribe(service)
        assert event_handler.service_for_sid('uuid:dummy') == service
        assert ok is True
        assert sid == 'uuid:dummy'

    @pytest.mark.asyncio
    async def test_unsubscribe(self):
        r = UpnpTestRequester(RESPONSE_MAP)
        factory = UpnpFactory(r)
        device = await factory.async_create_device('http://localhost:1234/dmr')
        event_handler = UpnpEventHandler('http://localhost:11302', r)

        service = device.service('urn:schemas-upnp-org:service:RenderingControl:1')
        ok, sid = await event_handler.async_subscribe(service)
        assert event_handler.service_for_sid('uuid:dummy') == service
        assert ok is True
        assert sid == 'uuid:dummy'

        ok, old_sid = await event_handler.async_unsubscribe(service)
        assert event_handler.service_for_sid('uuid:dummy') is None
        assert ok is True
        assert old_sid == 'uuid:dummy'

    @pytest.mark.asyncio
    async def test_on_notify_upnp_event(self):
        changed_vars = []

        def on_event(self, changed_state_variables):
            nonlocal changed_vars
            changed_vars = changed_state_variables

        r = UpnpTestRequester(RESPONSE_MAP)
        factory = UpnpFactory(r)
        device = await factory.async_create_device('http://localhost:1234/dmr')
        service = device.service('urn:schemas-upnp-org:service:RenderingControl:1')
        service.on_event = on_event
        event_handler = UpnpEventHandler('http://localhost:11302', r)
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

    @pytest.mark.asyncio
    async def test_on_notify_dlna_event(self):
        changed_vars = []

        def on_event(self, changed_state_variables):
            nonlocal changed_vars
            changed_vars += changed_state_variables

            assert changed_state_variables
            if changed_state_variables[0].name == 'LastChange':
                last_change = changed_state_variables[0]
                assert last_change.name == 'LastChange'

                dlna_handle_notify_last_change(last_change)

        r = UpnpTestRequester(RESPONSE_MAP)
        factory = UpnpFactory(r)
        device = await factory.async_create_device('http://localhost:1234/dmr')
        service = device.service('urn:schemas-upnp-org:service:RenderingControl:1')
        service.on_event = on_event
        event_handler = UpnpEventHandler('http://localhost:11302', r)
        await event_handler.async_subscribe(service)

        headers = {
            'NT': 'upnp:event',
            'NTS': 'upnp:propchange',
            'SID': 'uuid:dummy',
        }
        body = """
<e:propertyset xmlns:e="urn:schemas-upnp-org:event-1-0">
    <e:property>
        <LastChange>
            &lt;Event xmlns=&quot;urn:schemas-upnp-org:metadata-1-0/RCS/&quot;&gt;
                &lt;InstanceID val=&quot;0&quot;&gt;
                    &lt;Mute channel=&quot;Master&quot; val=&quot;0&quot;/&gt;
                    &lt;Volume channel=&quot;Master&quot; val=&quot;50&quot;/&gt;
                    &lt;/InstanceID&gt;
            &lt;/Event&gt;
        </LastChange>
    </e:property>
</e:propertyset>
"""

        result = await event_handler.handle_notify(headers, body)
        assert result == 200

        assert len(changed_vars) == 3

        state_var = service.state_variable('Volume')
        assert state_var.value == 50
