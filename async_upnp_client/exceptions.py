# -*- coding: utf-8 -*-
"""Exceptions raised by async_upnp_client."""

import asyncio
from typing import Any, Optional

import aiohttp

# pylint: disable=too-many-ancestors


class UpnpError(Exception):
    """UpnpError."""


class UpnpContentError(UpnpError):
    """Content of UPnP response is invalid."""


class UpnpValueError(UpnpContentError):
    """Invalid value error."""

    def __init__(self, name: str, value: Any) -> None:
        """Initialize."""
        super().__init__("Invalid value for %s: '%s'" % (name, value))
        self.name = name
        self.value = value


class UpnpSIDError(UpnpContentError):
    """Missing Subscription Identifier from response."""


class UpnpCommunicationError(UpnpError, aiohttp.ClientError):
    """Error occurred while communicating with the UPnP device ."""


class UpnpResponseError(UpnpCommunicationError):
    """HTTP error code returned by the UPnP device."""

    def __init__(
        self, status: int, headers: Optional[aiohttp.typedefs.LooseHeaders] = None
    ) -> None:
        """Initialize."""
        super().__init__("Did not receive HTTP 200 but {}".format(status))
        self.status = status
        self.headers = headers


class UpnpClientResponseError(aiohttp.ClientResponseError, UpnpResponseError):
    """HTTP response error with more details from aiohttp."""


class UpnpConnectionError(UpnpCommunicationError, aiohttp.ClientConnectionError):
    """Error in the underlying connection to the UPnP device.

    This could indicate that the device is offline.
    """


class UpnpConnectionTimeoutError(
    UpnpConnectionError, aiohttp.ServerTimeoutError, asyncio.TimeoutError
):
    """Timeout while communicating with the device."""


class UpnpServerError(UpnpError):
    """Error with a local server."""


class UpnpServerOSError(UpnpServerError, OSError):
    """System-related error when starting a local server."""

    def __init___(self, errno: int, strerror: str) -> None:
        """Initialize simplified version of OSError."""
        super().__init__(errno, strerror)
        self.errno = errno
        self.strerror = strerror
