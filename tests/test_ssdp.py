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


def test_decode_ssdp_packet_missing_ending():
    """Test SSDP response decoding with a missing end line."""
    msg = (
        b"HTTP/1.1 200 OK\r\n"
        b"CACHE-CONTROL: max-age = 1800\r\n"
        b"DATE:Sun, 25 Apr 2021 16:08:06 GMT\r\n"
        b"EXT:\r\n"
        b"LOCATION: http://192.168.107.148:8088/description\r\n"
        b"SERVER: Ubuntu/10.04 UPnP/1.1 Harmony/16.3\r\n"
        b"ST: urn:myharmony-com:device:harmony:1\r\n"
        b"USN: uuid:dc6a8cf155c97e5200c6a1a1997591756f2e2a3c::urn:myharmony-com:device:harmony:1\r\n"
        b"BOOTID.UPNP.ORG:1619366886\r\n"
    )
    request_line, headers = decode_ssdp_packet(msg, ("addr", 123))

    assert request_line == "HTTP/1.1 200 OK"

    assert headers == {
        "cache-control": "max-age = 1800",
        "date": "Sun, 25 Apr 2021 16:08:06 GMT",
        "location": "http://192.168.107.148:8088/description",
        "server": "Ubuntu/10.04 UPnP/1.1 Harmony/16.3",
        "st": "urn:myharmony-com:device:harmony:1",
        "usn": "uuid:dc6a8cf155c97e5200c6a1a1997591756f2e2a3c::urn:myharmony-com:device:harmony:1",
        "bootid.upnp.org": "1619366886",
        "ext": "",
        "_location_original": "http://192.168.107.148:8088/description",
        "_host": "addr",
        "_port": 123,
        "_udn": "uuid:dc6a8cf155c97e5200c6a1a1997591756f2e2a3c",
        "_timestamp": ANY,
    }


def test_decode_ssdp_packet_duplicate_header():
    """Test SSDP response decoding with a duplicate header."""
    msg = (
        b"HTTP/1.1 200 OK\r\n"
        b"CACHE-CONTROL: max-age = 1800\r\n"
        b"CACHE-CONTROL: max-age = 1800\r\n\r\n"
    )
    _, headers = decode_ssdp_packet(msg, ("addr", 123))

    assert headers == {
        "cache-control": "max-age = 1800",
        "_host": "addr",
        "_port": 123,
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
