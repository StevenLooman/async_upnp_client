#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Example to get the current volume from a DLNA/DMR capable TV.

Change the target variable below to point at your TV.
Use, for example, something like netdisco to discover the URL for the service.

You can run contrib/dummy_tv.py locally to emulate a TV.
"""

import asyncio
import logging

import aiohttp

from async_upnp_client import UpnpFactory
from async_upnp_client import UpnpRequester


logging.basicConfig(level=logging.INFO)


target = 'http://192.168.178.11:49152/description.xml'


class AioHttpRequester(UpnpRequester):
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


async def main():
    requester = AioHttpRequester()
    factory = UpnpFactory(requester)
    device = await factory.async_create_device(target)
    print("Device: {}".format(device))

    # get RenderingControle-service
    service = device.service('urn:schemas-upnp-org:service:RenderingControl:1')
    print("Service: {}".format(service))

    # perform GetVolume action
    get_volume = service.action('GetVolume')
    print("Action: {}".format(get_volume))
    result = await get_volume.async_call(InstanceID=0, Channel='Master')
    print("Action result: {}".format(result))


loop = asyncio.get_event_loop()
loop.run_until_complete(main())
