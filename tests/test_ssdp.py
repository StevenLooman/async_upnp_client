"""Unit tests for discovery."""
from unittest.mock import ANY

from async_upnp_client.ssdp import (
    build_ssdp_search_packet,
    decode_ssdp_packet,
    is_valid_ssdp_packet,
)


def test_ssdp_search_packet():
    """Test SSDP search packet generation."""
    msg = build_ssdp_search_packet(("239.255.255.250", 1900), 4, "ssdp:all")
    assert (
        msg == "M-SEARCH * HTTP/1.1\r\n"
        "HOST:239.255.255.250:1900\r\n"
        'MAN:"ssdp:discover"\r\n'
        "MX:4\r\n"
        "ST:ssdp:all\r\n"
        "\r\n".encode()
    )


def test_ssdp_search_packet_v6():
    """Test SSDP search packet generation."""
    msg = build_ssdp_search_packet(("FF02::C", 1900, 0, 2), 4, "ssdp:all")
    assert (
        msg == "M-SEARCH * HTTP/1.1\r\n"
        "HOST:[FF02::C%2]:1900\r\n"
        'MAN:"ssdp:discover"\r\n'
        "MX:4\r\n"
        "ST:ssdp:all\r\n"
        "\r\n".encode()
    )


def test_is_valid_ssdp_packet():
    """Test SSDP response validation."""
    assert not is_valid_ssdp_packet(b"")

    msg = (
        b"HTTP/1.1 200 OK\r\n"
        b"Cache-Control: max-age=1900\r\n"
        b"Location: http://192.168.1.1:80/RootDevice.xml\r\n"
        b"Server: UPnP/1.0 UPnP/1.0 UPnP-Device-Host/1.0\r\n"
        b"ST:urn:schemas-upnp-org:service:WANCommonInterfaceConfig:1\r\n"
        b"USN: uuid:...::WANCommonInterfaceConfig:1\r\n"
        b"EXT:\r\n\r\n"
    )
    assert is_valid_ssdp_packet(msg)


def test_decode_ssdp_packet():
    """Test SSDP response decoding."""
    msg = (
        b"HTTP/1.1 200 OK\r\n"
        b"Cache-Control: max-age=1900\r\n"
        b"Location: http://192.168.1.1:80/RootDevice.xml\r\n"
        b"Server: UPnP/1.0 UPnP/1.0 UPnP-Device-Host/1.0\r\n"
        b"ST:urn:schemas-upnp-org:service:WANCommonInterfaceConfig:1\r\n"
        b"USN: uuid:...::WANCommonInterfaceConfig:1\r\n"
        b"EXT:\r\n\r\n"
    )
    request_line, headers = decode_ssdp_packet(msg, ("addr", 123))

    assert request_line == "HTTP/1.1 200 OK"

    assert headers == {
        "cache-control": "max-age=1900",
        "location": "http://192.168.1.1:80/RootDevice.xml",
        "server": "UPnP/1.0 UPnP/1.0 UPnP-Device-Host/1.0",
        "st": "urn:schemas-upnp-org:service:WANCommonInterfaceConfig:1",
        "usn": "uuid:...::WANCommonInterfaceConfig:1",
        "ext": "",
        "_location_original": "http://192.168.1.1:80/RootDevice.xml",
        "_host": "addr",
        "_port": 123,
        "_udn": "uuid:...",
        "_timestamp": ANY,
    }


def test_decode_ssdp_packet_v6():
    """Test SSDP response decoding."""
    msg = (
        b"HTTP/1.1 200 OK\r\n"
        b"Cache-Control: max-age=1900\r\n"
        b"Location: http://[fe80::2]:80/RootDevice.xml\r\n"
        b"Server: UPnP/1.0 UPnP/1.0 UPnP-Device-Host/1.0\r\n"
        b"ST:urn:schemas-upnp-org:service:WANCommonInterfaceConfig:1\r\n"
        b"USN: uuid:...::WANCommonInterfaceConfig:1\r\n"
        b"EXT:\r\n\r\n"
    )

    request_line, headers = decode_ssdp_packet(msg, ("fe80::1", 123, 0, 3))

    assert request_line == "HTTP/1.1 200 OK"

    assert headers == {
        "cache-control": "max-age=1900",
        "location": "http://[fe80::2%3]:80/RootDevice.xml",
        "server": "UPnP/1.0 UPnP/1.0 UPnP-Device-Host/1.0",
        "st": "urn:schemas-upnp-org:service:WANCommonInterfaceConfig:1",
        "usn": "uuid:...::WANCommonInterfaceConfig:1",
        "ext": "",
        "_location_original": "http://[fe80::2]:80/RootDevice.xml",
        "_host": "fe80::1%3",
        "_port": 123,
        "_udn": "uuid:...",
        "_timestamp": ANY,
    }
