"""Unit tests for discovery."""

from async_upnp_client.ssdp import build_ssdp_search_packet
from async_upnp_client.ssdp import is_valid_ssdp_packet
from async_upnp_client.ssdp import decode_ssdp_packet


def test_ssdp_search_packet():
    msg = build_ssdp_search_packet(('239.255.255.250', 1900), 4, 'ssdp:all')
    assert msg == 'M-SEARCH * HTTP/1.1\r\n' \
           'HOST:239.255.255.250:1900\r\n' \
           'MAN:"ssdp:discover"\r\n' \
           'MX:4\r\n' \
           'ST:ssdp:all\r\n' \
           '\r\n'.encode()


def test_is_valid_ssdp_packet():
    assert not is_valid_ssdp_packet(b'')

    msg = b'HTTP/1.1 200 OK\r\n' \
          b'Cache-Control: max-age=1900\r\n' \
          b'Location: http://192.168.1.1:80/RootDevice.xml\r\n' \
          b'Server: UPnP/1.0 UPnP/1.0 UPnP-Device-Host/1.0\r\n' \
          b'ST:urn:schemas-upnp-org:service:WANCommonInterfaceConfig:1\r\n' \
          b'USN: uuid:...::WANCommonInterfaceConfig:1\r\n' \
          b'EXT:\r\n\r\n'
    assert is_valid_ssdp_packet(msg)


def test_decode_ssdp_packet():
    msg = b'HTTP/1.1 200 OK\r\n' \
          b'Cache-Control: max-age=1900\r\n' \
          b'Location: http://192.168.1.1:80/RootDevice.xml\r\n' \
          b'Server: UPnP/1.0 UPnP/1.0 UPnP-Device-Host/1.0\r\n' \
          b'ST:urn:schemas-upnp-org:service:WANCommonInterfaceConfig:1\r\n' \
          b'USN: uuid:...::WANCommonInterfaceConfig:1\r\n' \
          b'EXT:\r\n\r\n'
    request_line, headers = decode_ssdp_packet(msg, 'addr')

    assert request_line == 'HTTP/1.1 200 OK'

    # Remove variable things
    assert '_timestamp' in headers
    del headers['_timestamp']

    print(headers)
    assert headers == {
        'cache-control': 'max-age=1900',
        'location': 'http://192.168.1.1:80/RootDevice.xml',
        'server': 'UPnP/1.0 UPnP/1.0 UPnP-Device-Host/1.0',
        'st': 'urn:schemas-upnp-org:service:WANCommonInterfaceConfig:1',
        'usn': 'uuid:...::WANCommonInterfaceConfig:1',
        'ext': '',
        '_address': 'addr',
        '_udn': 'uuid:...',
    }
