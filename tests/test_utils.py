# -*- coding: utf-8 -*-
"""Unit tests for utils."""

from datetime import date, datetime, time, timedelta, timezone

from async_upnp_client.utils import CaseInsensitiveDict, parse_date_time, str_to_time

from .common import ADVERTISEMENT_HEADERS_DEFAULT


def test_case_insensitive_dict() -> None:
    """Test CaseInsensitiveDict."""
    ci_dict = CaseInsensitiveDict()
    ci_dict["Key"] = "value"
    assert ci_dict["Key"] == "value"
    assert ci_dict["key"] == "value"
    assert ci_dict["KEY"] == "value"

    assert CaseInsensitiveDict(key="value") == {"key": "value"}
    assert CaseInsensitiveDict({"key": "value"}, key="override_value") == {
        "key": "override_value"
    }


def test_case_insensitive_dict_dict_equality() -> None:
    """Test CaseInsensitiveDict against dict equality."""
    ci_dict = CaseInsensitiveDict()
    ci_dict["Key"] = "value"

    assert ci_dict == {"Key": "value"}
    assert ci_dict == {"key": "value"}
    assert ci_dict == {"KEY": "value"}


def test_case_insensitive_dict_profile() -> None:
    """Test CaseInsensitiveDict under load, for profiling."""
    for _ in range(0, 10000):
        assert (
            CaseInsensitiveDict(ADVERTISEMENT_HEADERS_DEFAULT)
            == ADVERTISEMENT_HEADERS_DEFAULT
        )


def test_case_insensitive_dict_equality() -> None:
    """Test CaseInsensitiveDict equality."""
    assert CaseInsensitiveDict(key="value") == CaseInsensitiveDict(KEY="value")


def test_str_to_time() -> None:
    """Test string to time parsing."""
    assert str_to_time("0:0:10") == timedelta(hours=0, minutes=0, seconds=10)
    assert str_to_time("0:10:0") == timedelta(hours=0, minutes=10, seconds=0)
    assert str_to_time("10:0:0") == timedelta(hours=10, minutes=0, seconds=0)

    assert str_to_time("0:0:10.10") == timedelta(
        hours=0, minutes=0, seconds=10, milliseconds=10
    )

    assert str_to_time("+0:0:10") == timedelta(hours=0, minutes=0, seconds=10)
    assert str_to_time("-0:0:10") == timedelta(hours=0, minutes=0, seconds=-10)

    assert str_to_time("") is None
    assert str_to_time(" ") is None


def test_parse_date_time() -> None:
    """Test string to datetime parsing."""
    tz0 = timezone(timedelta(hours=0))
    tz1 = timezone(timedelta(hours=1))
    assert parse_date_time("2012-07-19") == date(2012, 7, 19)
    assert parse_date_time("12:28:14") == time(12, 28, 14)
    assert parse_date_time("2012-07-19 12:28:14") == datetime(2012, 7, 19, 12, 28, 14)
    assert parse_date_time("2012-07-19T12:28:14") == datetime(2012, 7, 19, 12, 28, 14)
    assert parse_date_time("12:28:14+01:00") == time(12, 28, 14, tzinfo=tz1)
    assert parse_date_time("12:28:14 +01:00") == time(12, 28, 14, tzinfo=tz1)
    assert parse_date_time("2012-07-19T12:28:14z") == datetime(
        2012, 7, 19, 12, 28, 14, tzinfo=tz0
    )
    assert parse_date_time("2012-07-19T12:28:14Z") == datetime(
        2012, 7, 19, 12, 28, 14, tzinfo=tz0
    )
    assert parse_date_time("2012-07-19T12:28:14+01:00") == datetime(
        2012, 7, 19, 12, 28, 14, tzinfo=tz1
    )
    assert parse_date_time("2012-07-19T12:28:14 +01:00") == datetime(
        2012, 7, 19, 12, 28, 14, tzinfo=tz1
    )
