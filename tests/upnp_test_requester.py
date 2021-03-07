# -*- coding: utf-8 -*-
"""Profiles for upnp_client."""

import asyncio
import os.path
from copy import copy
from typing import Mapping, Tuple, Union

from async_upnp_client import UpnpRequester


def read_file(filename) -> str:
    """Read file."""
    path = os.path.join("tests", "fixtures", filename)
    with open(path, "r") as file:
        return file.read()


class UpnpTestRequester(UpnpRequester):
    """Test requester."""

    def __init__(self, response_map) -> None:
        """Class initializer."""
        self._response_map = copy(response_map)

    async def async_do_http_request(
        self, method, url, headers=None, body=None, body_type="text"
    ) -> Tuple[int, Mapping, Union[str, bytes, None]]:
        """Do a HTTP request."""
        # pylint: disable=too-many-arguments
        await asyncio.sleep(0.01)

        key = (method, url)
        if key not in self._response_map:
            raise Exception("Request not in response map")

        return self._response_map[key]


RESPONSE_MAP = {
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
        {"sid": "uuid:dummy"},
        "",
    ),
    ("UNSUBSCRIBE", "http://localhost:1234/upnp/event/RenderingControl1"): (
        200,
        {"sid": "uuid:dummy"},
        "",
    ),
}
