"""Unit tests for dlna."""

from typing import List

import pytest  # type: ignore

from async_upnp_client import UpnpEventHandler
from async_upnp_client import UpnpFactory
from async_upnp_client import UpnpStateVariable
from async_upnp_client.profiles.dlna import _parse_last_change_event
from async_upnp_client.profiles.dlna import dlna_handle_notify_last_change

from ..upnp_test_requester import UpnpTestRequester
from ..upnp_test_requester import RESPONSE_MAP


def test_parse_last_change_event():
    data = """<Event xmlns="urn:schemas-upnp-org:metadata-1-0/AVT/">
<InstanceID val="0"><TransportState val="PAUSED_PLAYBACK"/></InstanceID>
</Event>"""
    assert _parse_last_change_event(data) == {'0': {'TransportState': 'PAUSED_PLAYBACK'}}


def test_parse_last_change_event_multiple_instances():
    data = """<Event xmlns="urn:schemas-upnp-org:metadata-1-0/AVT/">
<InstanceID val="0"><TransportState val="PAUSED_PLAYBACK"/></InstanceID>
<InstanceID val="1"><TransportState val="PLAYING"/></InstanceID>
</Event>"""
    assert _parse_last_change_event(data) == {
        '0': {'TransportState': 'PAUSED_PLAYBACK'},
        '1': {'TransportState': 'PLAYING'},
    }


def test_parse_last_change_event_multiple_channels():
    data = """<Event xmlns="urn:schemas-upnp-org:metadata-1-0/AVT/">
<InstanceID val="0">
  <Volume channel="Master" val="10"/>
  <Volume channel="Left" val="20"/>
  <Volume channel="Right" val="30"/>
</InstanceID>
</Event>"""
    assert _parse_last_change_event(data) == {
        '0': {'Volume': '10'},
    }


def test_parse_last_change_event_invalid_xml():
    data = """<Event xmlns="urn:schemas-upnp-org:metadata-1-0/AVT/">
<InstanceID val="0"><TransportState val="PAUSED_PLAYBACK"></InstanceID>
</Event>"""
    assert _parse_last_change_event(data) == {'0': {'TransportState': 'PAUSED_PLAYBACK'}}


class TestUpnpEventHandler:

    @pytest.mark.asyncio
    async def test_on_notify_dlna_event(self):
        changed_vars = []  # type: List[UpnpStateVariable]

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
