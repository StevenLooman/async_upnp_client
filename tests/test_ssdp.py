"""Unit tests for ssdp."""
from ipaddress import IPv4Address
from unittest.mock import ANY

from async_upnp_client.ssdp import (
    SSDP_PORT,
    build_ssdp_search_packet,
    decode_ssdp_packet,
    get_ssdp_socket,
    is_valid_ssdp_packet,
)


def test_ssdp_search_packet() -> None:
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


def test_ssdp_search_packet_v6() -> None:
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


def test_is_valid_ssdp_packet() -> None:
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


def test_decode_ssdp_packet() -> None:
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


def test_decode_ssdp_packet_missing_ending() -> None:
    """Test SSDP response decoding with a missing end line."""
    msg = (
        b"HTTP/1.1 200 OK\r\n"
        b"CACHE-CONTROL: max-age = 1800\r\n"
        b"DATE:Sun, 25 Apr 2021 16:08:06 GMT\r\n"
        b"EXT:\r\n"
        b"LOCATION: http://192.168.107.148:8088/description\r\n"
        b"SERVER: Ubuntu/10.04 UPnP/1.1 Harmony/16.3\r\n"
        b"ST: urn:myharmony-com:device:harmony:1\r\n"
        b"USN: uuid:...::urn:myharmony-com:device:harmony:1\r\n"
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
        "usn": "uuid:...::urn:myharmony-com:device:harmony:1",
        "bootid.upnp.org": "1619366886",
        "ext": "",
        "_location_original": "http://192.168.107.148:8088/description",
        "_host": "addr",
        "_port": 123,
        "_udn": "uuid:...",
        "_timestamp": ANY,
    }


def test_decode_ssdp_packet_duplicate_header() -> None:
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


def test_decode_ssdp_packet_v6() -> None:
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


def test_get_ssdp_socket() -> None:
    """Test get_ssdp_socket accepts a port."""
    # Without a port, should default to SSDP_PORT
    _, source_info, target_info = get_ssdp_socket(
        IPv4Address("127.0.0.1"), IPv4Address("127.0.0.1")
    )
    assert source_info == ("127.0.0.1", 0)
    assert target_info == ("127.0.0.1", SSDP_PORT)

    # With a port
    _, source_info, target_info = get_ssdp_socket(
        IPv4Address("127.0.0.1"), IPv4Address("127.0.0.1"), 1234
    )
    assert source_info == ("127.0.0.1", 0)
    assert target_info == ("127.0.0.1", 1234)


def test_microsoft_butchers_ssdp() -> None:
    """Test parsing a `Microsoft Windows Peer Name Resolution Protocol` packet."""
    msg = (
        b"HTTP/1.1 200 OK\r\n"
        b"ST:urn:Microsoft Windows Peer Name Resolution Protocol: V4:IPV6:LinkLocal\r\n"
        b"USN:[fe80::aaaa:bbbb:cccc:dddd]:3540\r\n"
        b"Location:192.168.1.1\r\n"
        b"AL:[fe80::aaaa:bbbb:cccc:dddd]:3540\r\n"
        b'OPT:"http://schemas.upnp.org/upnp/1/0/"; ns=01\r\n'
        b"01-NLS:abcdef0123456789abcdef012345678\r\n"
        b"Cache-Control:max-age=14400\r\n"
        b"Server:Microsoft-Windows-NT/5.1 UPnP/1.0 UPnP-Device-Host/1.0\r\n"
        b"Ext:\r\n"
    )

    request_line, headers = decode_ssdp_packet(msg, ("192.168.1.1", 1900))

    assert request_line == "HTTP/1.1 200 OK"
    assert headers == {
        "st": "urn:Microsoft Windows Peer Name Resolution Protocol: V4:IPV6:LinkLocal",
        "usn": "[fe80::aaaa:bbbb:cccc:dddd]:3540",
        "location": "192.168.1.1",
        "al": "[fe80::aaaa:bbbb:cccc:dddd]:3540",
        "opt": '"http://schemas.upnp.org/upnp/1/0/"; ns=01',
        "01-nls": "abcdef0123456789abcdef012345678",
        "cache-control": "max-age=14400",
        "server": "Microsoft-Windows-NT/5.1 UPnP/1.0 UPnP-Device-Host/1.0",
        "ext": "",
        "_location_original": "192.168.1.1",
        "_host": "192.168.1.1",
        "_port": 1900,
        "_timestamp": ANY,
    }
