# -*- coding: utf-8 -*-
"""Description cache."""

import asyncio
import logging
from typing import Optional

import aiohttp

from async_upnp_client.client import UpnpRequester
from async_upnp_client.exceptions import UpnpResponseError

_LOGGER = logging.getLogger(__name__)


class DescriptionCache:
    """Cache for descriptions (xml)."""

    def __init__(self, requester: UpnpRequester):
        """Initialize."""
        self._requester = requester
        self._cache: dict[str, Optional[str]] = {}

    async def async_get_description(self, location: str) -> Optional[str]:
        """Get a description, either from cache or download it."""
        if location is None:
            return None
        if location not in self._cache:
            try:
                self._cache[location] = await self._async_fetch_description(location)
            except Exception:  # pylint: disable=broad-except
                # If it fails, cache the failure so we do not keep trying over and over
                self._cache[location] = None
                _LOGGER.exception("Failed to fetch description from: %s", location)

        return self._cache[location]

    async def _async_fetch_description(self, location: str) -> Optional[str]:
        """Download a description from location."""
        try:
            for _ in range(2):
                status, headers, body = await self._requester.async_http_request(
                    "GET", location
                )
                if status != 200:
                    raise UpnpResponseError(status=status, headers=headers)
                return body
                # Samsung Smart TV sometimes returns an empty document the
                # first time. Retry once.
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            _LOGGER.debug("Error fetching %s: %s", location, err)

        return None
