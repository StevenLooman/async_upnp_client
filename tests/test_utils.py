"""Unit tests for dlna."""

from datetime import timedelta

from async_upnp_client.utils import CaseInsensitiveDict
from async_upnp_client.utils import str_to_time


def test_case_insensitive_dict():
    ci = CaseInsensitiveDict()
    ci['Key'] = 'value'
    assert ci['Key'] == 'value'
    assert ci['key'] == 'value'
    assert ci['KEY'] == 'value'

    assert ci == {'Key': 'value'}
    assert ci == {'key': 'value'}
    assert ci == {'KEY': 'value'}

    source_dict = {'key': 'value'}
    ci = CaseInsensitiveDict(**source_dict)
    assert ci == {'key': 'value'}


def test_str_to_time():
    assert str_to_time('0:0:10') == timedelta(hours=0, minutes=0, seconds=10)
    assert str_to_time('0:10:0') == timedelta(hours=0, minutes=10, seconds=0)
    assert str_to_time('10:0:0') == timedelta(hours=10, minutes=0, seconds=0)

    assert str_to_time('0:0:10.10') == timedelta(hours=0, minutes=0, seconds=10, milliseconds=10)

    assert str_to_time('+0:0:10') == timedelta(hours=0, minutes=0, seconds=10)
    assert str_to_time('-0:0:10') == timedelta(hours=0, minutes=0, seconds=-10)

    assert str_to_time('') is None
    assert str_to_time(' ') is None
