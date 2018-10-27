"""Unit tests for discovery."""

from async_upnp_client.discovery import _discovery_message
from async_upnp_client.discovery import _parse_response


def test_discovery_message():
    msg = _discovery_message(('239.255.255.250', 1900), 4, 'ssdp:all')
    assert msg == 'M-SEARCH * HTTP/1.1\r\n' \
           'HOST:239.255.255.250:1900\r\n' \
           'MAN:"ssdp:discover"\r\n' \
           'MX:4\r\n' \
           'ST:ssdp:all\r\n' \
           '\r\n'.encode()

def test_parse_response():
    msg = b'HTTP/1.1 200 OK\r\n' \
          b'Cache-Control: max-age=1900\r\n' \
          b'Location: http://192.168.1.1:80/RootDevice.xml\r\n' \
          b'Server: UPnP/1.0 UPnP/1.0 UPnP-Device-Host/1.0\r\n' \
          b'ST:urn:schemas-upnp-org:service:WANCommonInterfaceConfig:1\r\n' \
          b'USN: uuid:...:WANCommonInterfaceConfig:1\r\n' \
          b'EXT:\r\n\r\n'
    response = _parse_response(msg)

    assert '_timestamp' in response

    del response['_timestamp']  # Remove variable things
    assert response == {
        'cache-control': 'max-age=1900',
        'location': 'http://192.168.1.1:80/RootDevice.xml',
        'server': 'UPnP/1.0 UPnP/1.0 UPnP-Device-Host/1.0',
        'st': 'urn:schemas-upnp-org:service:WANCommonInterfaceConfig:1',
        'usn': 'uuid:...:WANCommonInterfaceConfig:1',
        'ext': '',
    }
