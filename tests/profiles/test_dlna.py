"""Unit tests for dlna."""

from typing import List, Sequence

import pytest

from async_upnp_client import UpnpEventHandler, UpnpFactory, UpnpStateVariable
from async_upnp_client.client import UpnpService
from async_upnp_client.profiles.dlna import (
    _parse_last_change_event,
    dlna_handle_notify_last_change,
)

from ..upnp_test_requester import RESPONSE_MAP, UpnpTestRequester


def test_parse_last_change_event() -> None:
    """Test parsing a last change event."""
    data = """<Event xmlns="urn:schemas-upnp-org:metadata-1-0/AVT/">
<InstanceID val="0"><TransportState val="PAUSED_PLAYBACK"/></InstanceID>
</Event>"""
    assert _parse_last_change_event(data) == {
        "0": {"TransportState": "PAUSED_PLAYBACK"}
    }


def test_parse_last_change_event_multiple_instances() -> None:
    """Test parsing a last change event with multiple instance."""
    data = """<Event xmlns="urn:schemas-upnp-org:metadata-1-0/AVT/">
<InstanceID val="0"><TransportState val="PAUSED_PLAYBACK"/></InstanceID>
<InstanceID val="1"><TransportState val="PLAYING"/></InstanceID>
</Event>"""
    assert _parse_last_change_event(data) == {
        "0": {"TransportState": "PAUSED_PLAYBACK"},
        "1": {"TransportState": "PLAYING"},
    }


def test_parse_last_change_event_multiple_channels() -> None:
    """Test parsing a last change event with multiple channels."""
    data = """<Event xmlns="urn:schemas-upnp-org:metadata-1-0/AVT/">
<InstanceID val="0">
  <Volume channel="Master" val="10"/>
  <Volume channel="Left" val="20"/>
  <Volume channel="Right" val="30"/>
</InstanceID>
</Event>"""
    assert _parse_last_change_event(data) == {
        "0": {"Volume": "10"},
    }


def test_parse_last_change_event_invalid_xml() -> None:
    """Test parsing an invalid (non valid XML) last change event."""
    data = """<Event xmlns="urn:schemas-upnp-org:metadata-1-0/AVT/">
<InstanceID val="0"><TransportState val="PAUSED_PLAYBACK"></InstanceID>
</Event>"""
    assert _parse_last_change_event(data) == {
        "0": {"TransportState": "PAUSED_PLAYBACK"}
    }


@pytest.mark.asyncio
async def test_on_notify_dlna_event() -> None:
    """Test handling an event.."""
    changed_vars: List[UpnpStateVariable] = []

    def on_event(
        _self: UpnpService, changed_state_variables: Sequence[UpnpStateVariable]
    ) -> None:
        nonlocal changed_vars
        changed_vars += changed_state_variables

        assert changed_state_variables
        if changed_state_variables[0].name == "LastChange":
            last_change = changed_state_variables[0]
            assert last_change.name == "LastChange"

            dlna_handle_notify_last_change(last_change)

    requester = UpnpTestRequester(RESPONSE_MAP)
    factory = UpnpFactory(requester)
    device = await factory.async_create_device("http://localhost:1234/dmr")
    service = device.service("urn:schemas-upnp-org:service:RenderingControl:1")
    service.on_event = on_event
    event_handler = UpnpEventHandler("http://localhost:11302", requester)
    await event_handler.async_subscribe(service)

    headers = {
        "NT": "upnp:event",
        "NTS": "upnp:propchange",
        "SID": "uuid:dummy",
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

    state_var = service.state_variable("Volume")
    assert state_var.value == 50
