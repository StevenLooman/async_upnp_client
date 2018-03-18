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

from async_upnp_client import UpnpFactory
from async_upnp_client import AioHttpRequester


logging.basicConfig(level=logging.DEBUG)
_LOGGER = logging.getLogger(__name__)


target = 'http://localhost:8000/dmr'


def main():
    requester = AioHttpRequester()
    factory = UpnpFactory(requester)
    device = yield from factory.async_create_device(target)

    # get RenderingControle-service
    rc = device.service('urn:schemas-upnp-org:service:RenderingControl:1')

    # perform GetVolume action
    get_volume = rc.action('GetVolume')
    print("Action: {}".format(get_volume))
    result = yield from get_volume.async_call(InstanceID=0, Channel='Master')
    print("Action result: {}".format(result))


loop = asyncio.get_event_loop()
loop.run_until_complete(main())
