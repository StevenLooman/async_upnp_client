# -*- coding: utf-8 -*-
"""aiohttp requester module."""

import asyncio
import logging
import socket

import aiohttp
import aiohttp.web
import async_timeout

from async_upnp_client import UpnpRequester
from async_upnp_client import UpnpEventHandler


_LOGGER = logging.getLogger(__name__)


def get_local_ip(target_host=None) -> str:
    """Try to get the local IP of this machine, used to talk to target_url."""
    target_host = target_host or '8.8.8.8'
    target_port = 80

    try:
        temp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        temp_sock.connect((target_host, target_port))
        return temp_sock.getsockname()[0]
    finally:
        temp_sock.close()


class AiohttpRequester(UpnpRequester):
    """Standard AioHttpUpnpRequester, to be used with UpnpFactory."""

    def __init__(self, timeout=5) -> None:
        """Initializer."""
        self._timeout = timeout

    async def async_do_http_request(self, method, url, headers=None, body=None, body_type='text'):
        """Do a HTTP request."""
        # pylint: disable=too-many-arguments

        async with async_timeout.timeout(self._timeout):
            async with aiohttp.ClientSession() as session:
                async with session.request(method, url, headers=headers, data=body) as response:
                    status = response.status
                    headers = response.headers

                    if body_type == 'text':
                        body = await response.text()
                    elif body_type == 'raw':
                        body = await response.read()
                    elif body_type == 'ignore':
                        body = None

        return status, headers, body


class AiohttpSessionRequester(UpnpRequester):
    """
    Standard AiohttpSessionRequester, to be used with UpnpFactory.

    With pluggable session.
    """

    def __init__(self, session, with_sleep=False, timeout=5) -> None:
        """Initializer."""
        self._session = session
        self._with_sleep = with_sleep
        self._timeout = timeout

    async def async_do_http_request(self, method, url, headers=None, body=None, body_type='text'):
        """Do a HTTP request."""
        # pylint: disable=too-many-arguments

        if self._with_sleep:
            await asyncio.sleep(0.01)

        async with async_timeout.timeout(self._timeout):
            async with self._session.request(method, url, headers=headers, data=body) as response:
                status = response.status
                headers = response.headers

                if body_type == 'text':
                    body = await response.text()
                elif body_type == 'raw':
                    body = await response.read()
                elif body_type == 'ignore':
                    body = None

        return status, headers, body


class AiohttpNotifyServer:
    """AIO HTTP Server to handle incoming events."""

    def __init__(self, requester, listen_port, listen_host=None, loop=None) -> None:
        """Initializer."""
        self._listen_port = listen_port
        self._listen_host = listen_host or get_local_ip()
        self._loop = loop or asyncio.get_event_loop()

        self._aiohttp_server = None
        self._server = None

        callback_url = "http://{}:{}/notify".format(self._listen_host, self._listen_port)
        self.event_handler = UpnpEventHandler(callback_url, requester)

    async def start_server(self):
        """Start the HTTP server."""
        self._aiohttp_server = aiohttp.web.Server(self._handle_request)
        try:
            self._server = await self._loop.create_server(self._aiohttp_server,
                                                          self._listen_host,
                                                          self._listen_port)
        except OSError as error:
            _LOGGER.error("Failed to create HTTP server at %s:%d: %s",
                          self._listen_host, self._listen_port, error)

    async def stop_server(self):
        """Stop the HTTP server."""
        if self._aiohttp_server:
            await self._aiohttp_server.shutdown(10)

        if self._server:
            self._server.close()

    async def _handle_request(self, request) -> aiohttp.web.Response:
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
