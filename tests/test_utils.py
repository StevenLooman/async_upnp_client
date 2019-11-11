"""Unit tests for dlna."""

from datetime import date, datetime, time, timedelta, timezone

from async_upnp_client.utils import CaseInsensitiveDict
from async_upnp_client.utils import str_to_time
from async_upnp_client.utils import parse_date_time


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

    cis = set()
    cis.add(CaseInsensitiveDict(key='value'))
    cis.add(CaseInsensitiveDict(KEY='value'))
    assert len(cis) == 1


def test_str_to_time():
    assert str_to_time('0:0:10') == timedelta(hours=0, minutes=0, seconds=10)
    assert str_to_time('0:10:0') == timedelta(hours=0, minutes=10, seconds=0)
    assert str_to_time('10:0:0') == timedelta(hours=10, minutes=0, seconds=0)

    assert str_to_time('0:0:10.10') == timedelta(hours=0, minutes=0, seconds=10, milliseconds=10)

    assert str_to_time('+0:0:10') == timedelta(hours=0, minutes=0, seconds=10)
    assert str_to_time('-0:0:10') == timedelta(hours=0, minutes=0, seconds=-10)

    assert str_to_time('') is None
    assert str_to_time(' ') is None

def test_parse_date_time():
    tz0 = timezone(timedelta(hours=0))
    tz1 = timezone(timedelta(hours=1))
    assert parse_date_time('2012-07-19') == date(2012, 7, 19)
    assert parse_date_time('12:28:14') == time(12, 28, 14)
    assert parse_date_time('2012-07-19 12:28:14') == datetime(2012, 7, 19, 12, 28, 14)
    assert parse_date_time('2012-07-19T12:28:14') == datetime(2012, 7, 19, 12, 28, 14)
    assert parse_date_time('12:28:14+01:00') == time(12, 28, 14, tzinfo=tz1)
    assert parse_date_time('12:28:14 +01:00') == time(12, 28, 14, tzinfo=tz1)
    assert parse_date_time('2012-07-19T12:28:14z') == datetime(2012, 7, 19, 12, 28, 14, tzinfo=tz0)
    assert parse_date_time('2012-07-19T12:28:14Z') == datetime(2012, 7, 19, 12, 28, 14, tzinfo=tz0)
    assert parse_date_time('2012-07-19T12:28:14+01:00') == datetime(2012, 7, 19, 12, 28, 14, tzinfo=tz1)
    assert parse_date_time('2012-07-19T12:28:14 +01:00') == datetime(2012, 7, 19, 12, 28, 14, tzinfo=tz1)
