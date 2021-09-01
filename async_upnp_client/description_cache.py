# -*- coding: utf-8 -*-
"""Description cache."""

import asyncio
import logging
from typing import Mapping, Optional

import aiohttp
import defusedxml.ElementTree as DET

from async_upnp_client.client import UpnpRequester
from async_upnp_client.exceptions import UpnpResponseError
from async_upnp_client.utils import etree_to_dict

_LOGGER = logging.getLogger(__name__)


def _description_xml_to_dict(description_xml: str) -> Optional[Mapping[str, str]]:
    """Convert description (XML) to dict."""
    try:
        tree = DET.fromstring(description_xml)
    except DET.ParseError as err:
        _LOGGER.debug("Error parsing %s: %s", description_xml, err)
        return None

    root = etree_to_dict(tree).get("root")
    if root is None:
        return None

    return root.get("device")


class DescriptionCache:
    """Cache for descriptions (xml)."""

    def __init__(self, requester: UpnpRequester):
        """Initialize."""
        self._requester = requester
        self._cache_xml: dict[str, Optional[str]] = {}
        self._cache_dict: dict[str, Optional[Mapping[str, str]]] = {}

    async def async_get_description_xml(self, location: str) -> Optional[str]:
        """Get a description as XML, either from cache or download it."""
        if location is None:
            return None

        if location not in self._cache_xml:
            try:
                self._cache_xml[location] = await self._async_fetch_description(
                    location
                )
            except Exception:  # pylint: disable=broad-except
                # If it fails, cache the failure so we do not keep trying over and over
                self._cache_xml[location] = None
                _LOGGER.exception("Failed to fetch description from: %s", location)

        return self._cache_xml[location]

    async def async_get_description_dict(
        self, location: Optional[str]
    ) -> Optional[Mapping[str, str]]:
        """Get a description as dict, either from cache or download it."""
        if location is None:
            return None

        if location not in self._cache_dict:
            description_xml = await self.async_get_description_xml(location)
            if description_xml:
                self._cache_dict[location] = _description_xml_to_dict(description_xml)
            else:
                self._cache_dict[location] = None

        return self._cache_dict[location]

    def uncache_description(self, location: str) -> None:
        """Uncache a description."""
        if location in self._cache_xml:
            del self._cache_xml[location]
        if location in self._cache_dict:
            del self._cache_dict[location]

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
