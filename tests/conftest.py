# -*- coding: utf-8 -*-
"""Conftest."""

import asyncio
import os.path
from collections import deque
from copy import deepcopy
from typing import Deque, Mapping, MutableMapping, Optional, Tuple, cast

from async_upnp_client import UpnpNotifyServer, UpnpRequester


def read_fixture(filename: str) -> str:
    """Read file."""
    path = os.path.join("tests", "fixtures", filename)
    with open(path, encoding="utf-8") as file:
        return file.read()


class UpnpTestRequester(UpnpRequester):
    """Test requester."""

    # pylint: disable=too-few-public-methods

    def __init__(
        self,
        response_map: Mapping[Tuple[str, str], Tuple[int, Mapping[str, str], str]],
    ) -> None:
        """Initialize."""
        self.response_map: MutableMapping[
            Tuple[str, str],
            Tuple[int, MutableMapping[str, str], str],
        ] = deepcopy(cast(MutableMapping, response_map))
        self.exceptions: Deque[Optional[Exception]] = deque()

    async def async_http_request(
        self,
        method: str,
        url: str,
        headers: Optional[Mapping[str, str]] = None,
        body: Optional[str] = None,
    ) -> Tuple[int, Mapping, str]:
        """Do a HTTP request."""
        await asyncio.sleep(0.01)

        if self.exceptions:
            exception = self.exceptions.popleft()
            if exception is not None:
                raise exception

        key = (method, url)
        if key not in self.response_map:
            raise KeyError(f"Request not in response map: {key}")

        return self.response_map[key]


class UpnpTestNotifyServer(UpnpNotifyServer):
    """Test notify server."""

    # pylint: disable=too-few-public-methods

    def __init__(self, callback_url: Optional[str] = None) -> None:
        """Initialize."""
        self._callback_url = callback_url or "http://192.168.1.2:8000/notify"

    @property
    def callback_url(self) -> str:
        """Return callback URL on which we are callable."""
        return self._callback_url


RESPONSE_MAP: Mapping[Tuple[str, str], Tuple[int, Mapping[str, str], str]] = {
    # DLNA/DMR
    ("GET", "http://dlna_dmr:1234/device.xml"): (
        200,
        {},
        read_fixture("dlna/dmr/device.xml"),
    ),
    ("GET", "http://dlna_dmr:1234/device_embedded.xml"): (
        200,
        {},
        read_fixture("dlna/dmr/device_embedded.xml"),
    ),
    ("GET", "http://dlna_dmr:1234/device_incomplete.xml"): (
        200,
        {},
        read_fixture("dlna/dmr/device_incomplete.xml"),
    ),
    ("GET", "http://dlna_dmr:1234/RenderingControl_1.xml"): (
        200,
        {},
        read_fixture("dlna/dmr/RenderingControl_1.xml"),
    ),
    ("GET", "http://dlna_dmr:1234/ConnectionManager_1.xml"): (
        200,
        {},
        read_fixture("dlna/dmr/ConnectionManager_1.xml"),
    ),
    ("GET", "http://dlna_dmr:1234/AVTransport_1.xml"): (
        200,
        {},
        read_fixture("dlna/dmr/AVTransport_1.xml"),
    ),
    ("SUBSCRIBE", "http://dlna_dmr:1234/upnp/event/RenderingControl1"): (
        200,
        {"sid": "uuid:dummy", "timeout": "Second-300"},
        "",
    ),
    ("SUBSCRIBE", "http://dlna_dmr:1234/upnp/event/AVTransport1"): (
        200,
        {"sid": "uuid:dummy-avt1", "timeout": "Second-150"},
        "",
    ),
    ("UNSUBSCRIBE", "http://dlna_dmr:1234/upnp/event/RenderingControl1"): (
        200,
        {"sid": "uuid:dummy"},
        "",
    ),
    ("UNSUBSCRIBE", "http://dlna_dmr:1234/upnp/event/AVTransport1"): (
        200,
        {"sid": "uuid:dummy-avt1"},
        "",
    ),
    # IGD
    ("GET", "http://igd:1234/device.xml"): (200, {}, read_fixture("igd/device.xml")),
    ("GET", "http://igd:1234/Layer3Forwarding.xml"): (
        200,
        {},
        read_fixture("igd/Layer3Forwarding.xml"),
    ),
    ("GET", "http://igd:1234/WANCommonInterfaceConfig.xml"): (
        200,
        {},
        read_fixture("igd/WANCommonInterfaceConfig.xml"),
    ),
    ("GET", "http://igd:1234/WANIPConnection.xml"): (
        200,
        {},
        read_fixture("igd/WANIPConnection.xml"),
    ),
}