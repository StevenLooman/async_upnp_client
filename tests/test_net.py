# -*- coding: utf-8 -*-
"""Unit tests for net."""

import sys
from ipaddress import IPv4Address, IPv6Address
from unittest.mock import patch

import pytest
from async_upnp_client.const import AddressTupleVXType

from async_upnp_client.net import (
    get_adjusted_url,
    get_host_port_string,
    get_host_string,
    get_source_address_tuple,
    get_source_address_tuple_for_location,
    ip_address_from_address_tuple,
    ip_address_str_from_address_tuple,
)
from async_upnp_client.ssdp import SSDP_IP_V4, SSDP_IP_V6, SSDP_PORT


def test_get_host_string() -> None:
    """Test get_host_string()."""
    assert get_host_string((SSDP_IP_V4, SSDP_PORT)) == SSDP_IP_V4
    assert get_host_string((SSDP_IP_V6, SSDP_PORT, 0, 0)) == SSDP_IP_V6
    assert get_host_string((SSDP_IP_V6, SSDP_PORT, 0, 4)) == "FF02::C%4"


def test_get_host_port_string() -> None:
    """Test get_host_port_string()."""
    assert get_host_port_string((SSDP_IP_V4, SSDP_PORT)) == "239.255.255.250:1900"
    assert get_host_port_string((SSDP_IP_V6, SSDP_PORT, 0, 0)) == "[FF02::C]:1900"
    assert get_host_port_string((SSDP_IP_V6, SSDP_PORT, 0, 4)) == "[FF02::C]:1900"


def test_get_adjusted_url() -> None:
    """Test get_adjusted_url()."""
    assert (
        get_adjusted_url("http://192.168.1.1/desc.xml", ("192.168.1.1", 1900))
        == "http://192.168.1.1/desc.xml"
    )
    assert (
        get_adjusted_url("http://[fe80::1]/desc.xml", ("fe80::1", 1900, 0, 0))
        == "http://[fe80::1]/desc.xml"
    )
    assert (
        get_adjusted_url("http://bork/desc.xml", ("fe80::1", 1900, 0, 0))
        == "http://bork/desc.xml"
    )
    assert (
        get_adjusted_url("http://[2002::1]/desc.xml", ("fe80::1", 1900, 0, 3))
        == "http://[2002::1]/desc.xml"
    )
    assert (
        get_adjusted_url("http://[fe80::1]/desc.xml", ("fe80::1", 1900, 0, 3))
        == "http://[fe80::1%3]/desc.xml"
    )
    assert (
        get_adjusted_url("http://[fe80::1]:1902/desc.xml", ("fe80::1", 1900, 0, 3))
        == "http://[fe80::1%3]:1902/desc.xml"
    )


def test_ip_address_from_address_tuple() -> None:
    """Test get IPvXAddress from AddressTupleVXType."""
    assert ip_address_from_address_tuple(("192.168.1.1", SSDP_PORT)) == IPv4Address(
        "192.168.1.1"
    )
    assert ip_address_from_address_tuple(("fe80::1", SSDP_PORT, 0, 0)) == IPv6Address(
        "fe80::1"
    )
    if sys.version_info >= (
        3,
        9,
    ):
        assert ip_address_from_address_tuple(
            ("fe80::1", SSDP_PORT, 0, 2)
        ) == IPv6Address("fe80::1%2")
    else:
        assert ip_address_from_address_tuple(
            ("fe80::1", SSDP_PORT, 0, 2)
        ) == IPv6Address("fe80::1")


def test_ip_address_str_from_address_tuple() -> None:
    """Test ip_address_str_from_address_tuple()."""
    assert (
        ip_address_str_from_address_tuple(("192.168.1.1", SSDP_PORT)) == "192.168.1.1"
    )
    assert ip_address_str_from_address_tuple(("fe80::1", SSDP_PORT, 0, 0)) == "fe80::1"
    assert (
        ip_address_str_from_address_tuple(("fe80::1", SSDP_PORT, 0, 2)) == "fe80::1%2"
    )


def test_get_source_address_tuple() -> None:
    """Test get_source_address_tuple()."""
    target = ("not_important", SSDP_PORT)
    assert get_source_address_tuple(target, ("192.168.1.1", 0)) == ("192.168.1.1", 0)
    assert get_source_address_tuple(target, ("fe80::1", 0, 0, 0)) == (
        "fe80::1",
        0,
        0,
        0,
    )
    assert get_source_address_tuple(target, ("fe80::1", 0, 0, 2)) == (
        "fe80::1",
        0,
        0,
        2,
    )
    assert get_source_address_tuple(target, IPv4Address("192.168.1.1")) == (
        "192.168.1.1",
        0,
    )
    assert get_source_address_tuple(target, IPv6Address("fe80::1")) == (
        "fe80::1",
        0,
        0,
        0,
    )
    with patch('async_upnp_client.net.get_local_ip', return_value="192.168.1.1"):
        assert get_source_address_tuple((SSDP_IP_V4, SSDP_PORT)) == ("192.168.1.1", 0)
    
    with patch('async_upnp_client.net.get_local_ip', return_value="fe80::1"):
        assert get_source_address_tuple((SSDP_IP_V6, SSDP_PORT, 0, 0)) == ("fe80::1", 0, 0, 0)
        assert get_source_address_tuple((SSDP_IP_V6, SSDP_PORT, 0, 3)) == ("fe80::1", 0, 0, 3)

    if sys.version_info >= (
        3,
        9,
    ):
        assert get_source_address_tuple(target, IPv6Address("fe80::1%1")) == (
            "fe80::1",
            0,
            0,
            1,
        )


@pytest.mark.parametrize("location,expected", [
    ("http://192.168.1.1/igddesc.xml", ("192.168.1.2", 0)),
    ("http://[fe80::1]/igddesc.xml", ("fe80::2", 0, 0, 0)),
])
def test_get_source_address_tuple_for_location(location: str, expected: AddressTupleVXType) -> None:
    """Test get_source_address_tuple_for_location()."""
    with patch("async_upnp_client.net.get_local_ip", return_value=expected[0]):
        assert get_source_address_tuple_for_location(location) == expected
