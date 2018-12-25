"""Unit tests for dlna."""

from async_upnp_client.dlna import _parse_last_change_event


def test_parse_last_change_event():
    data = """<Event xmlns="urn:schemas-upnp-org:metadata-1-0/AVT/">
<InstanceID val="0"><TransportState val="PAUSED_PLAYBACK"/></InstanceID>
</Event>"""
    assert _parse_last_change_event(data) == {'0': {'TransportState': 'PAUSED_PLAYBACK'}}


def test_parse_last_change_event_2():
    data = """<Event xmlns="urn:schemas-upnp-org:metadata-1-0/AVT/">
<InstanceID val="0"><TransportState val="PAUSED_PLAYBACK"/></InstanceID>
<InstanceID val="1"><TransportState val="PLAYING"/></InstanceID>
</Event>"""
    assert _parse_last_change_event(data) == {
        '0': {'TransportState': 'PAUSED_PLAYBACK'},
        '1': {'TransportState': 'PLAYING'},
    }


def test_parse_last_change_event_invalid_xml():
    data = """<Event xmlns="urn:schemas-upnp-org:metadata-1-0/AVT/">
<InstanceID val="0"><TransportState val="PAUSED_PLAYBACK"></InstanceID>
</Event>"""
    assert _parse_last_change_event(data) == {'0': {'TransportState': 'PAUSED_PLAYBACK'}}
