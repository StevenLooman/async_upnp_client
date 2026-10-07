"""Profiles for upnp_client."""

import asyncio
import os.path
from collections import deque
from copy import deepcopy
from typing import Collection, Deque, Mapping, MutableMapping, cast

from async_upnp_client.client import UpnpRequester
from async_upnp_client.const import AddressTupleVXType, HttpRequest, HttpResponse
from async_upnp_client.event_handler import UpnpEventHandler, UpnpNotifyServer


def read_file(filename: str) -> str:
    """Read file."""
    path = os.path.join("tests", "fixtures", filename)
    with open(path, encoding="utf-8") as file:
        return file.read()


class UpnpTestRequester(UpnpRequester):
    """Test requester."""

    # pylint: disable=too-few-public-methods

    def __init__(
        self,
        response_map: Mapping[tuple[str, str], HttpResponse],
    ) -> None:
        """Class initializer."""
        self.response_map: MutableMapping[tuple[str, str], HttpResponse] = deepcopy(cast(MutableMapping, response_map))
        self.exceptions: Deque[Exception | None] = deque()

    async def async_http_request(
        self,
        http_request: HttpRequest,
    ) -> HttpResponse:
        """Do a HTTP request."""
        await asyncio.sleep(0.01)

        if self.exceptions:
            exception = self.exceptions.popleft()
            if exception is not None:
                raise exception

        key = (http_request.method, http_request.url)
        if key not in self.response_map:
            raise KeyError(f"Request not in response map: {key}")

        return self.response_map[key]


class RecordingRequester(UpnpTestRequester):
    """Test requester that records the requests it handles.

    Actions named in `empty_responses` are answered with an empty SOAP response, so a test
    can call them without a response fixture per action.
    """

    def __init__(
        self,
        response_map: Mapping[tuple[str, str], HttpResponse],
        empty_responses: Collection[str] = (),
    ) -> None:
        """Class initializer."""
        super().__init__(response_map)
        self.empty_responses = frozenset(empty_responses)
        self.requests: list[HttpRequest] = []

    @staticmethod
    def _soap_action(http_request: HttpRequest) -> tuple[str, str] | None:
        """Return (service type, action name) from the SOAPAction header, if any."""
        soap_action = (http_request.headers or {}).get("SOAPAction", "").strip('"')
        if "#" not in soap_action:
            return None
        service_type, action_name = soap_action.split("#", 1)
        return service_type, action_name

    async def async_http_request(
        self,
        http_request: HttpRequest,
    ) -> HttpResponse:
        """Record the request, then answer it."""
        self.requests.append(http_request)
        soap_action = self._soap_action(http_request)
        if soap_action and soap_action[1] in self.empty_responses:
            service_type, action_name = soap_action
            body = (
                '<?xml version="1.0"?>'
                '<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/"'
                ' s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/"><s:Body>'
                f'<u:{action_name}Response xmlns:u="{service_type}"></u:{action_name}Response>'
                "</s:Body></s:Envelope>"
            )
            return HttpResponse(200, {}, body)
        return await super().async_http_request(http_request)

    def last_request(self, action_name: str) -> HttpRequest:
        """Return the most recent request for the given SOAP action."""
        for http_request in reversed(self.requests):
            soap_action = self._soap_action(http_request)
            if soap_action and soap_action[1] == action_name:
                return http_request
        raise AssertionError(f"No request for action {action_name}")


RESPONSE_MAP: Mapping[tuple[str, str], HttpResponse] = {
    # DLNA/DMR
    ("GET", "http://dlna_dmr:1234/device.xml"): HttpResponse(
        200,
        {},
        read_file("dlna/dmr/device.xml"),
    ),
    ("GET", "http://dlna_dmr:1234/device_embedded.xml"): HttpResponse(
        200,
        {},
        read_file("dlna/dmr/device_embedded.xml"),
    ),
    ("GET", "http://dlna_dmr:1234/device_incomplete.xml"): HttpResponse(
        200,
        {},
        read_file("dlna/dmr/device_incomplete.xml"),
    ),
    ("GET", "http://dlna_dmr:1234/device_with_empty_descriptor.xml"): HttpResponse(
        200,
        {},
        read_file("dlna/dmr/device_with_empty_descriptor.xml"),
    ),
    ("GET", "http://dlna_dmr:1234/RenderingControl_1.xml"): HttpResponse(
        200,
        {},
        read_file("dlna/dmr/RenderingControl_1.xml"),
    ),
    ("GET", "http://dlna_dmr:1234/ConnectionManager_1.xml"): HttpResponse(
        200,
        {},
        read_file("dlna/dmr/ConnectionManager_1.xml"),
    ),
    ("GET", "http://dlna_dmr:1234/AVTransport_1.xml"): HttpResponse(
        200,
        {},
        read_file("dlna/dmr/AVTransport_1.xml"),
    ),
    ("GET", "http://dlna_dmr:1234/Empty_Descriptor.xml"): HttpResponse(
        200,
        {},
        read_file("dlna/dmr/Empty_Descriptor.xml"),
    ),
    ("SUBSCRIBE", "http://dlna_dmr:1234/upnp/event/ConnectionManager1"): HttpResponse(
        200,
        {"sid": "uuid:dummy-cm1", "timeout": "Second-175"},
        "",
    ),
    ("SUBSCRIBE", "http://dlna_dmr:1234/upnp/event/RenderingControl1"): HttpResponse(
        200,
        {"sid": "uuid:dummy", "timeout": "Second-300"},
        "",
    ),
    ("SUBSCRIBE", "http://dlna_dmr:1234/upnp/event/AVTransport1"): HttpResponse(
        200,
        {"sid": "uuid:dummy-avt1", "timeout": "Second-150"},
        "",
    ),
    ("SUBSCRIBE", "http://dlna_dmr:1234/upnp/event/QPlay"): HttpResponse(
        200,
        {"sid": "uuid:dummy-qp1", "timeout": "Second-150"},
        "",
    ),
    ("UNSUBSCRIBE", "http://dlna_dmr:1234/upnp/event/ConnectionManager1"): HttpResponse(
        200,
        {"sid": "uuid:dummy-cm1"},
        "",
    ),
    ("UNSUBSCRIBE", "http://dlna_dmr:1234/upnp/event/RenderingControl1"): HttpResponse(
        200,
        {"sid": "uuid:dummy"},
        "",
    ),
    ("UNSUBSCRIBE", "http://dlna_dmr:1234/upnp/event/AVTransport1"): HttpResponse(
        200,
        {"sid": "uuid:dummy-avt1"},
        "",
    ),
    ("UNSUBSCRIBE", "http://dlna_dmr:1234/upnp/event/QPlay"): HttpResponse(
        200,
        {"sid": "uuid:dummy-qp1"},
        "",
    ),
    # DLNA/DMS
    ("GET", "http://dlna_dms:1234/device.xml"): HttpResponse(
        200,
        {},
        read_file("dlna/dms/device.xml"),
    ),
    ("GET", "http://dlna_dms:1234/ConnectionManager_1.xml"): HttpResponse(
        200,
        {},
        read_file("dlna/dms/ConnectionManager_1.xml"),
    ),
    ("GET", "http://dlna_dms:1234/ContentDirectory_1.xml"): HttpResponse(
        200,
        {},
        read_file("dlna/dms/ContentDirectory_1.xml"),
    ),
    ("SUBSCRIBE", "http://dlna_dms:1234/upnp/event/ConnectionManager1"): HttpResponse(
        200,
        {"sid": "uuid:dummy-cm1", "timeout": "Second-150"},
        "",
    ),
    ("SUBSCRIBE", "http://dlna_dms:1234/upnp/event/ContentDirectory1"): HttpResponse(
        200,
        {"sid": "uuid:dummy-cd1", "timeout": "Second-150"},
        "",
    ),
    ("UNSUBSCRIBE", "http://dlna_dms:1234/upnp/event/ConnectionManager1"): HttpResponse(
        200,
        {"sid": "uuid:dummy-cm1"},
        "",
    ),
    ("UNSUBSCRIBE", "http://dlna_dms:1234/upnp/event/ContentDirectory1"): HttpResponse(
        200,
        {"sid": "uuid:dummy-cd1"},
        "",
    ),
    # IGD
    ("GET", "http://igd:1234/device.xml"): HttpResponse(200, {}, read_file("igd/device.xml")),
    ("GET", "http://igd:1234/Layer3Forwarding.xml"): HttpResponse(
        200,
        {},
        read_file("igd/Layer3Forwarding.xml"),
    ),
    ("GET", "http://igd:1234/WANCommonInterfaceConfig.xml"): HttpResponse(
        200,
        {},
        read_file("igd/WANCommonInterfaceConfig.xml"),
    ),
    ("GET", "http://igd:1234/WANIPConnection.xml"): HttpResponse(
        200,
        {},
        read_file("igd/WANIPConnection.xml"),
    ),
}


class UpnpTestNotifyServer(UpnpNotifyServer):
    """Test notify server."""

    def __init__(
        self,
        requester: UpnpRequester,
        source: AddressTupleVXType,
        callback_url: str | None = None,
    ) -> None:
        """Initialize."""
        self._requester = requester
        self._source = source
        self._callback_url = callback_url
        self.event_handler = UpnpEventHandler(self, requester)

    @property
    def callback_url(self) -> str:
        """Return callback URL on which we are callable."""
        return self._callback_url or f"http://{self._source[0]}:{self._source[1]}/notify"

    async def async_start_server(self) -> None:
        """Start the server."""

    async def async_stop_server(self) -> None:
        """Stop the server."""
        await self.event_handler.async_unsubscribe_all()
