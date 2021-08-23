# -*- coding: utf-8 -*-
"""Profiles for upnp_client."""

import asyncio
import os.path
from collections import deque
from copy import deepcopy
from typing import Deque, Mapping, MutableMapping, Optional, Tuple, cast

from async_upnp_client import UpnpRequester


def read_file(filename: str) -> str:
    """Read file."""
    path = os.path.join("tests", "fixtures", filename)
    with open(path, encoding="utf-8") as file:
        return file.read()


class UpnpTestRequester(UpnpRequester):
    """Test requester."""

    def __init__(
        self,
        response_map: Mapping[Tuple[str, str], Tuple[int, Mapping[str, str], str]],
    ) -> None:
        """Class initializer."""
        self.response_map: MutableMapping[
            Tuple[str, str],
            Tuple[int, MutableMapping[str, str], str],
        ] = deepcopy(cast(MutableMapping, response_map))
        self.exceptions: Deque[Optional[Exception]] = deque()

    async def async_do_http_request(
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


RESPONSE_MAP: Mapping[Tuple[str, str], Tuple[int, Mapping[str, str], str]] = {
    ("GET", "http://localhost:1234/dmr"): (200, {}, read_file("dmr")),
    ("GET", "http://localhost:1234/RenderingControl_1.xml"): (
        200,
        {},
        read_file("RenderingControl_1.xml"),
    ),
    ("GET", "http://localhost:1234/AVTransport_1.xml"): (
        200,
        {},
        read_file("AVTransport_1.xml"),
    ),
    ("SUBSCRIBE", "http://localhost:1234/upnp/event/RenderingControl1"): (
        200,
        {"sid": "uuid:dummy", "timeout": "Second-300"},
        "",
    ),
    ("SUBSCRIBE", "http://localhost:1234/upnp/event/AVTransport1"): (
        200,
        {"sid": "uuid:dummy-avt1", "timeout": "Second-150"},
        "",
    ),
    ("UNSUBSCRIBE", "http://localhost:1234/upnp/event/RenderingControl1"): (
        200,
        {"sid": "uuid:dummy"},
        "",
    ),
    ("UNSUBSCRIBE", "http://localhost:1234/upnp/event/AVTransport1"): (
        200,
        {"sid": "uuid:dummy-avt1"},
        "",
    ),
}
