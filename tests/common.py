"""Common test parts."""

from datetime import datetime

from async_upnp_client.utils import CaseInsensitiveDict

ADVERTISEMENT_REQUEST_LINE = "NOTIFY * HTTP/1.1"
ADVERTISEMENT_HEADERS_DEFAULT = CaseInsensitiveDict(
    {
        "CACHE-CONTROL": "max-age=1800",
        "NTS": "ssdp:alive",
        "NT": "urn:schemas-upnp-org:service:WANCommonInterfaceConfig:1",
        "USN": "uuid:...::urn:schemas-upnp-org:service:WANCommonInterfaceConfig:1",
        "LOCATION": "http://192.168.1.1:80/RootDevice.xml",
        "BOOTID.UPNP.ORG": "1",
        "SERVER": "Linux/2.0 UPnP/1.0 async_upnp_client/0.1",
        "_timestamp": datetime.now(),
        "_host": "192.168.1.1",
        "_port": "1900",
        "_udn": "uuid:...",
    }
)
SEARCH_REQUEST_LINE = "HTTP/1.1 200 OK"
SEARCH_HEADERS_DEFAULT = CaseInsensitiveDict(
    {
        "CACHE-CONTROL": "max-age=1800",
        "ST": "urn:schemas-upnp-org:service:WANCommonInterfaceConfig:1",
        "USN": "uuid:...::urn:schemas-upnp-org:service:WANCommonInterfaceConfig:1",
        "LOCATION": "http://192.168.1.1:80/RootDevice.xml",
        "BOOTID.UPNP.ORG": "1",
        "SERVER": "Linux/2.0 UPnP/1.0 async_upnp_client/0.1",
        "DATE": "Fri, 1 Jan 2021 12:00:00 GMT",
        "_timestamp": datetime.now(),
        "_host": "192.168.1.1",
        "_port": "1900",
        "_udn": "uuid:...",
    }
)

DISCOVERY_REQUEST_LINE = "M-SEARCH * HTTP/1.1"
