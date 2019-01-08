# -*- coding: utf-8 -*-
"""aiohttp requester module."""

import asyncio
from asyncio.events import AbstractEventLoop
from asyncio.events import AbstractServer  # noqa: F401
import logging
import socket
from typing import Any, Mapping, Optional, Tuple, Union  # noqa: F401

import aiohttp
import aiohttp.web
import async_timeout

from async_upnp_client import UpnpRequester
from async_upnp_client import UpnpEventHandler


_LOGGER = logging.getLogger(__name__)


EXTERNAL_IP = '1.1.1.1'


def get_local_ip(target_host: Optional[str] = None) -> str:
    """Try to get the local IP of this machine, used to talk to target_url."""
    target_host = target_host or EXTERNAL_IP
    target_port = 80

    try:
        temp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        temp_sock.connect((target_host, target_port))
        local_ip = temp_sock.getsockname()[0]  # type: str
        return local_ip
    finally:
        temp_sock.close()


class AiohttpRequester(UpnpRequester):
    """Standard AioHttpUpnpRequester, to be used with UpnpFactory."""

    def __init__(self, timeout: int = 5) -> None:
        """Initializer."""
        self._timeout = timeout

    async def async_do_http_request(self,
                                    method: str,
                                    url: str,
                                    headers: Optional[Mapping[str, str]] = None,
                                    body: Optional[str] = None,
                                    body_type: str = 'text') \
            -> Tuple[int, Mapping, Union[str, bytes, None]]:
        """Do a HTTP request."""
        # pylint: disable=too-many-arguments

        async with async_timeout.timeout(self._timeout):
            async with aiohttp.ClientSession() as session:
                async with session.request(method, url, headers=headers, data=body) as response:
                    status = response.status
                    resp_headers = response.headers or {}

                    resp_body = None  # type: Union[str, bytes, None]
                    if body_type == 'text':
                        resp_body = await response.text()
                    elif body_type == 'raw':
                        resp_body = await response.read()
                    elif body_type == 'ignore':
                        resp_body = None

        return status, resp_headers, resp_body


class AiohttpSessionRequester(UpnpRequester):
    """
    Standard AiohttpSessionRequester, to be used with UpnpFactory.

    With pluggable session.
    """

    def __init__(self,
                 session: aiohttp.ClientSession,
                 with_sleep: bool = False,
                 timeout: int = 5) -> None:
        """Initializer."""
        self._session = session
        self._with_sleep = with_sleep
        self._timeout = timeout

    async def async_do_http_request(self,
                                    method: str,
                                    url: str,
                                    headers: Optional[Mapping[str, str]] = None,
                                    body: Optional[str] = None,
                                    body_type: str = 'text') \
            -> Tuple[int, Mapping, Union[str, bytes, None]]:
        """Do a HTTP request."""
        # pylint: disable=too-many-arguments

        if self._with_sleep:
            await asyncio.sleep(0.01)

        async with async_timeout.timeout(self._timeout):
            async with self._session.request(method, url, headers=headers, data=body) as response:
                status = response.status
                resp_headers = response.headers or {}

                resp_body = None  # type: Union[str, bytes, None]
                if body_type == 'text':
                    resp_body = await response.text()
                elif body_type == 'raw':
                    resp_body = await response.read()
                elif body_type == 'ignore':
                    resp_body = None

        return status, resp_headers, resp_body


class AiohttpNotifyServer:
    """AIO HTTP Server to handle incoming events."""

    def __init__(self,
                 requester: UpnpRequester,
                 listen_port: int,
                 listen_host: Optional[str] = None,
                 loop: Optional[AbstractEventLoop] = None) -> None:
        """Initializer."""
        self._listen_port = listen_port
        self._listen_host = listen_host or get_local_ip()
        self._loop = loop or asyncio.get_event_loop()

        self._aiohttp_server = None  # type: Optional[aiohttp.web.Server]
        self._server = None  # type: Optional[AbstractServer]

        callback_url = "http://{}:{}/notify".format(self._listen_host, self._listen_port)
        self.event_handler = UpnpEventHandler(callback_url, requester)

    async def start_server(self) -> None:
        """Start the HTTP server."""
        self._aiohttp_server = aiohttp.web.Server(self._handle_request)
        try:
            self._server = await self._loop.create_server(self._aiohttp_server,
                                                          self._listen_host,
                                                          self._listen_port)
        except OSError as error:
            _LOGGER.error("Failed to create HTTP server at %s:%d: %s",
                          self._listen_host, self._listen_port, error)

    async def stop_server(self) -> None:
        """Stop the HTTP server."""
        if self._aiohttp_server:
            await self._aiohttp_server.shutdown(10)

        if self._server:
            self._server.close()

    async def _handle_request(self, request: Any) \
            -> aiohttp.web.Response:
        """Handle incoming requests."""
        _LOGGER.debug('Received request: %s', request)
        if request.method != 'NOTIFY':
            _LOGGER.debug('Not notify')
            return aiohttp.web.Response(status=405)

        headers = request.headers
        body = await request.text()

        status = await self.event_handler.handle_notify(headers, body)
        _LOGGER.debug('NOTIFY response status: %s', status)
        return aiohttp.web.Response(status=status)

    @property
    def callback_url(self) -> str:
        """Return callback URL on which we are callable."""
        return self.event_handler.callback_url
