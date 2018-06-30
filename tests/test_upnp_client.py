"""Unit tests for upnp_client."""

import asyncio
import os.path

import pytest
import voluptuous as vol
import xml.etree.ElementTree as ET

from async_upnp_client import (
    UpnpError,
    UpnpFactory,
    UpnpRequester
)
from async_upnp_client.utils import dlna_handle_notify_last_change


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
        self._response_map = response_map

    async def async_http_request(self, method, url, headers=None, body=None):
        await asyncio.sleep(0.01)

        key = (method, url)
        if key not in self._response_map:
            raise Exception('Request not in response map')

        return self._response_map[key]


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
        except vol.error.MultipleInvalid:
            pass

        try:
            sv.value = 110
            assert False
        except vol.error.MultipleInvalid:
            pass

    @pytest.mark.asyncio
    async def test_value_min_max_ignore(self):
        r = UpnpTestRequester(RESPONSE_MAP)
        factory = UpnpFactory(r, ignore_state_variable_value_range=True)
        device = await factory.async_create_device('http://localhost:1234/dmr')
        service = device.service('urn:schemas-upnp-org:service:RenderingControl:1')
        sv = service.state_variable('Volume')

        assert sv.min_value is None
        assert sv.max_value is None

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
        except vol.error.MultipleInvalid:
            pass

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
        except vol.error.MultipleInvalid:
            pass

        # missing DesiredVolume
        try:
            action.validate_arguments(InstanceID='0', Channel='Master')
            assert False
        except vol.error.MultipleInvalid:
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
    async def test_subscribe(self):
        r = UpnpTestRequester(RESPONSE_MAP)
        factory = UpnpFactory(r)
        device = await factory.async_create_device('http://localhost:1234/dmr')
        service = device.service('urn:schemas-upnp-org:service:RenderingControl:1')

        callback_uri = 'http://callback_uri'
        sid = 'uuid:dummy'

        received_sid = await service.async_subscribe(callback_uri)
        assert sid == received_sid
        assert sid == service.subscription_sid

    @pytest.mark.asyncio
    async def test_unsubscribe(self):
        r = UpnpTestRequester(RESPONSE_MAP)
        factory = UpnpFactory(r)
        device = await factory.async_create_device('http://localhost:1234/dmr')
        service = device.service('urn:schemas-upnp-org:service:RenderingControl:1')
        service._subscription_sid = 'uuid:dummy'

        assert service.subscription_sid == 'uuid:dummy'
        await service.async_unsubscribe()
        assert service.subscription_sid is None

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

    @pytest.mark.asyncio
    async def test_on_notify_upnp_event(self):
        changed_vars = []

        def change_handler(self, changed_state_variables):
            nonlocal changed_vars
            changed_vars = changed_state_variables

        r = UpnpTestRequester(RESPONSE_MAP)
        factory = UpnpFactory(r)
        device = await factory.async_create_device('http://localhost:1234/dmr')
        service = device.service('urn:schemas-upnp-org:service:RenderingControl:1')
        service._subscription_sid = 'uuid:e540ce62-7be8-11e8-b1a6-a619ad6a4b38'
        service.on_state_variable_change = change_handler

        headers = {
            'NT': 'upnp:event',
            'NTS': 'upnp:propchange',
            'SID': service._subscription_sid,
        }
        body = """
<e:propertyset xmlns:e="urn:schemas-upnp-org:event-1-0">
    <e:property>
        <Volume>60</Volume>
    </e:property>
</e:propertyset>
"""
        result = service.on_notify(headers, body)
        assert result == 200
        assert changed_vars

        state_var = service.state_variable('Volume')
        assert state_var.value == 60

    @pytest.mark.asyncio
    async def test_on_notify_dlna_event(self):
        changed_vars = []

        def change_handler(self, changed_state_variables):
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
        service._subscription_sid = 'uuid:e540ce62-7be8-11e8-b1a6-a619ad6a4b38'
        service.on_state_variable_change = change_handler

        headers = {
            'NT': 'upnp:event',
            'NTS': 'upnp:propchange',
            'SID': service._subscription_sid,
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

        result = service.on_notify(headers, body)
        assert result == 200

        state_var = service.state_variable('Volume')
        assert state_var.value == 50
