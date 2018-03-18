# -*- coding: utf-8 -*-
"""AIOHTTP module for use with UpnpFactory."""

import aiohttp
import asyncio
import logging

from async_upnp_client import UpnpRequester


_LOGGER = logging.getLogger(__name__)


class AioHttpRequester(UpnpRequester):
    """Standard AioHttpUpnpRequester, to be used with UpnpFactory."""

    async def async_http_request(self, method, url, headers=None, body=None):
        """Do a HTTP request."""
        async with aiohttp.ClientSession() as session:
            async with session.request(method, url, headers=headers, data=body) as response:
                status = response.status
                headers = response.headers
                body = await response.text()

        return status, headers, body
