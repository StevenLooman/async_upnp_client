"""Unit tests for dlna."""

from datetime import timedelta

from async_upnp_client.dlna import _str_to_time
from async_upnp_client.dlna import _parse_last_change_event


def test_str_to_time():
    assert _str_to_time('0:0:10') == timedelta(hours=0, minutes=0, seconds=10)
    assert _str_to_time('0:10:0') == timedelta(hours=0, minutes=10, seconds=0)
    assert _str_to_time('10:0:0') == timedelta(hours=10, minutes=0, seconds=0)

    assert _str_to_time('0:0:10.10') == timedelta(hours=0, minutes=0, seconds=10, milliseconds=10)

    assert _str_to_time('+0:0:10') == timedelta(hours=0, minutes=0, seconds=10)
    assert _str_to_time('-0:0:10') == timedelta(hours=0, minutes=0, seconds=-10)

    assert _str_to_time('') is None
    assert _str_to_time(' ') is None


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
