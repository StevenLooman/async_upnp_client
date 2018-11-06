"""Unit tests for dlna."""

from datetime import timedelta

from async_upnp_client.dlna import _str_to_time


def test_str_to_time():
    assert _str_to_time('0:0:10') == timedelta(hours=0, minutes=0, seconds=10)
    assert _str_to_time('0:10:0') == timedelta(hours=0, minutes=10, seconds=0)
    assert _str_to_time('10:0:0') == timedelta(hours=10, minutes=0, seconds=0)

    assert _str_to_time('0:0:10.10') == timedelta(hours=0, minutes=0, seconds=10, milliseconds=10)

    assert _str_to_time('+0:0:10') == timedelta(hours=0, minutes=0, seconds=10)
    assert _str_to_time('-0:0:10') == timedelta(hours=0, minutes=0, seconds=-10)

    assert _str_to_time('') is None
    assert _str_to_time(' ') is None
