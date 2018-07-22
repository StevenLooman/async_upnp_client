# -*- coding: utf-8 -*-
"""aiohttp requester module."""

import asyncio

import aiohttp

from async_upnp_client import UpnpRequester


class AiohttpRequester(UpnpRequester):
    """Standard AioHttpUpnpRequester, to be used with UpnpFactory."""

    async def async_do_http_request(self, method, url, headers=None, body=None, body_type='text'):
        """Do a HTTP request."""
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
    """Standard AioHttpUpnpRequester, to be used with UpnpFactory."""

    def __init__(self, session, with_sleep=False):
        self._session = session
        self._with_sleep = with_sleep

    async def async_do_http_request(self, method, url, headers=None, body=None, body_type='text'):
        """Do a HTTP request."""

        if self._with_sleep:
            await asyncio.sleep(0.01)

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
