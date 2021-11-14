# -*- coding: utf-8 -*-
"""aiohttp requester module."""

import asyncio
import logging
from asyncio.events import AbstractEventLoop, AbstractServer
from socket import AddressFamily  # pylint: disable=no-name-in-module
from typing import Any, Mapping, Optional, Tuple

import aiohttp
import aiohttp.web
import async_timeout

from async_upnp_client import UpnpEventHandler, UpnpRequester
from async_upnp_client.exceptions import (
    UpnpClientResponseError,
    UpnpCommunicationError,
    UpnpConnectionError,
    UpnpConnectionTimeoutError,
    UpnpServerOSError,
)

_LOGGER = logging.getLogger(__name__)
_LOGGER_TRAFFIC_UPNP = logging.getLogger("async_upnp_client.traffic.upnp")


class AiohttpRequester(UpnpRequester):
    """Standard AioHttpUpnpRequester, to be used with UpnpFactory."""

    # pylint: disable=too-few-public-methods

    def __init__(
        self, timeout: int = 5, http_headers: Optional[Mapping[str, str]] = None
    ) -> None:
        """Initialize."""
        self._timeout = timeout
        self._http_headers = http_headers or {}

    async def async_http_request(
        self,
        method: str,
        url: str,
        headers: Optional[Mapping[str, str]] = None,
        body: Optional[str] = None,
    ) -> Tuple[int, Mapping, str]:
        """Do a HTTP request."""
        req_headers = {**self._http_headers, **(headers or {})}

        _LOGGER_TRAFFIC_UPNP.debug(
            "Sending request:\n%s %s\n%s\n%s\n",
            method,
            url,
            "\n".join(
                [key + ": " + value for key, value in (req_headers or {}).items()]
            ),
            body or "",
        )

        try:
            async with async_timeout.timeout(self._timeout):
                async with aiohttp.ClientSession() as session:
                    async with session.request(
                        method, url, headers=req_headers, data=body
                    ) as response:
                        status = response.status
                        resp_headers: Mapping = response.headers or {}
                        resp_body = await response.read()

                        _LOGGER_TRAFFIC_UPNP.debug(
                            "Got response:\n%s\n%s\n\n%s",
                            status,
                            "\n".join(
                                [
                                    key + ": " + value
                                    for key, value in resp_headers.items()
                                ]
                            ),
                            resp_body,
                        )

                        resp_body_text = await response.text()
        except asyncio.TimeoutError as err:
            raise UpnpConnectionTimeoutError(str(err)) from err
        except aiohttp.ClientConnectionError as err:
            raise UpnpConnectionError(str(err)) from err
        except aiohttp.ClientResponseError as err:
            raise UpnpClientResponseError(
                request_info=err.request_info,
                history=err.history,
                status=err.status,
                message=err.message,
                headers=err.headers,
            ) from err
        except aiohttp.ClientError as err:
            raise UpnpCommunicationError(str(err)) from err
        except UnicodeDecodeError as err:
            raise UpnpCommunicationError(str(err)) from err

        return status, resp_headers, resp_body_text


class AiohttpSessionRequester(UpnpRequester):
    """
    Standard AiohttpSessionRequester, to be used with UpnpFactory.

    With pluggable session.
    """

    # pylint: disable=too-few-public-methods

    def __init__(
        self,
        session: aiohttp.ClientSession,
        with_sleep: bool = False,
        timeout: int = 5,
        http_headers: Optional[Mapping[str, str]] = None,
    ) -> None:
        """Initialize."""
        self._session = session
        self._with_sleep = with_sleep
        self._timeout = timeout
        self._http_headers = http_headers or {}

    async def async_http_request(
        self,
        method: str,
        url: str,
        headers: Optional[Mapping[str, str]] = None,
        body: Optional[str] = None,
    ) -> Tuple[int, Mapping[str, str], str]:
        """Do a HTTP request with a retry on ServerDisconnectedError.

        The HTTP/1.1 spec allows the server to disconnect at any time.
        We want to retry the request in this event.
        """
        for _ in range(2):
            try:
                return await self._async_http_request(method, url, headers, body)
            except aiohttp.ServerDisconnectedError as err:
                _LOGGER.debug("%r during request; retrying", err)
        try:
            return await self._async_http_request(method, url, headers, body)
        except aiohttp.ServerDisconnectedError as err:
            raise UpnpConnectionError(str(err)) from err

    async def _async_http_request(
        self,
        method: str,
        url: str,
        headers: Optional[Mapping[str, str]] = None,
        body: Optional[str] = None,
    ) -> Tuple[int, Mapping[str, str], str]:
        """Do a HTTP request."""
        # pylint: disable=too-many-arguments
        req_headers = {**self._http_headers, **(headers or {})}

        _LOGGER_TRAFFIC_UPNP.debug(
            "Sending request:\n%s %s\n%s\n%s\n",
            method,
            url,
            "\n".join(
                [key + ": " + value for key, value in (req_headers or {}).items()]
            ),
            body or "",
        )

        if self._with_sleep:
            await asyncio.sleep(0)

        try:
            async with async_timeout.timeout(self._timeout):
                async with self._session.request(
                    method, url, headers=req_headers, data=body
                ) as response:
                    status = response.status
                    resp_headers: Mapping = response.headers or {}
                    resp_body = await response.read()

                    _LOGGER_TRAFFIC_UPNP.debug(
                        "Got response:\n%s\n%s\n\n%s",
                        status,
                        "\n".join(
                            [key + ": " + value for key, value in resp_headers.items()]
                        ),
                        resp_body,
                    )

                    resp_body_text = await response.text()
        except asyncio.TimeoutError as err:
            raise UpnpConnectionTimeoutError(str(err)) from err
        except aiohttp.ServerDisconnectedError:
            raise
        except aiohttp.ClientConnectionError as err:
            raise UpnpConnectionError(str(err)) from err
        except aiohttp.ClientResponseError as err:
            raise UpnpClientResponseError(
                request_info=err.request_info,
                history=err.history,
                status=err.status,
                message=err.message,
                headers=err.headers,
            ) from err
        except aiohttp.ClientError as err:
            raise UpnpCommunicationError(str(err)) from err
        except UnicodeDecodeError as err:
            raise UpnpCommunicationError(str(err)) from err

        return status, resp_headers, resp_body_text


class AiohttpNotifyServer:
    """AIO HTTP Server to handle incoming events."""

    CALLBACK_URL_FMT = "http://{host}:{port}/notify"

    def __init__(
        self,
        requester: UpnpRequester,
        listen_port: int = 0,
        listen_host: Optional[str] = None,
        callback_url: Optional[str] = None,
        loop: Optional[AbstractEventLoop] = None,
    ) -> None:
        """Initialize."""
        # pylint: disable=too-many-arguments
        self._listen_port = listen_port
        self._listen_host = listen_host
        self._loop = loop or asyncio.get_event_loop()

        self._aiohttp_server: Optional[aiohttp.web.Server] = None
        self._server: Optional[AbstractServer] = None

        # callback_url may contain format fields for filling in once the server
        # is started and listening ports are known
        callback_url = callback_url or self.CALLBACK_URL_FMT
        callback_url = callback_url.format(
            host=self._listen_host or "{host}",
            port=self._listen_port or "{port}",
        )
        self.event_handler = UpnpEventHandler(callback_url, requester)

    async def start_server(self) -> None:
        """Start the HTTP server."""
        self._aiohttp_server = aiohttp.web.Server(self._handle_request)
        try:
            self._server = await self._loop.create_server(
                self._aiohttp_server, self._listen_host, self._listen_port
            )
        except OSError as err:
            _LOGGER.error(
                "Failed to create HTTP server at %s:%d: %s",
                self._listen_host,
                self._listen_port,
                err,
            )
            raise UpnpServerOSError(
                errno=err.errno,
                strerror=err.strerror,
            ) from err

        # All ports that the event server is listening on (maybe multiple IP stacks)
        if self._server.sockets:
            listen_ports = {
                AddressFamily(sock.family): sock.getsockname()[1]
                for sock in self._server.sockets
            }
        else:
            _LOGGER.warning("No listening sockets for AiohttpNotifyServer")
            listen_ports = {}

        # Set event_handler's listen_ports  for it to format the callback_url correctly
        _LOGGER.debug("event_handler listening on %s", listen_ports)
        self.event_handler.listen_ports = listen_ports

    async def stop_server(self) -> None:
        """Stop the HTTP server."""
        await self.event_handler.async_unsubscribe_all()
        self.event_handler.listen_ports = {}

        if self._aiohttp_server:
            await self._aiohttp_server.shutdown(10)
            self._aiohttp_server = None

        if self._server:
            self._server.close()
            self._server = None

    async def _handle_request(self, request: Any) -> aiohttp.web.Response:
        """Handle incoming requests."""
        _LOGGER.debug("Received request: %s", request)

        headers = request.headers
        body = await request.text()
        _LOGGER_TRAFFIC_UPNP.debug(
            "Incoming request:\nNOTIFY\n%s\n\n%s",
            "\n".join([key + ": " + value for key, value in headers.items()]),
            body,
        )

        if request.method != "NOTIFY":
            _LOGGER.debug("Not notify")
            return aiohttp.web.Response(status=405)

        if not self.event_handler:
            _LOGGER.debug("Event handler not created yet")
            return aiohttp.web.Response(status=503, reason="Server not fully started")

        status = await self.event_handler.handle_notify(headers, body)
        _LOGGER.debug("NOTIFY response status: %s", status)
        _LOGGER_TRAFFIC_UPNP.debug("Sending response: %s", status)

        return aiohttp.web.Response(status=status)

    @property
    def callback_url(self) -> str:
        """Return callback URL on which we are callable."""
        return self.event_handler.callback_url
