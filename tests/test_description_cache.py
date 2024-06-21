"""Unit tests for description_cache."""

import asyncio
from unittest.mock import patch

import aiohttp
import defusedxml.ElementTree as DET
import pytest

from async_upnp_client.const import HttpResponse
from async_upnp_client.description_cache import DescriptionCache

from .conftest import UpnpTestRequester


@pytest.mark.asyncio
async def test_fetch_parse_success() -> None:
    """Test properly fetching and parsing a description."""
    xml = """<root xmlns="urn:schemas-upnp-org:device-1-0">
  <device>
    <deviceType>urn:schemas-upnp-org:device:TestDevice:1</deviceType>
    <UDN>uuid:test_udn</UDN>
  </device>
</root>"""
    requester = UpnpTestRequester(
        {("GET", "http://192.168.1.1/desc.xml"): HttpResponse(200, {}, xml)}
    )
    description_cache = DescriptionCache(requester)
    descr_xml = await description_cache.async_get_description_xml(
        "http://192.168.1.1/desc.xml"
    )
    assert descr_xml == xml

    descr_dict = await description_cache.async_get_description_dict(
        "http://192.168.1.1/desc.xml"
    )
    assert descr_dict == {
        "deviceType": "urn:schemas-upnp-org:device:TestDevice:1",
        "UDN": "uuid:test_udn",
    }


@pytest.mark.asyncio
async def test_fetch_parse_success_invalid_chars() -> None:
    """Test fail parsing a description with invalid characters."""
    xml = """<root xmlns="urn:schemas-upnp-org:device-1-0">
  <device>
    <deviceType>urn:schemas-upnp-org:device:TestDevice:1</deviceType>
    <UDN>uuid:test_udn</UDN>
    <serialNumber>\xff\xff\xff\xff</serialNumber>
  </device>
</root>"""
    requester = UpnpTestRequester(
        {("GET", "http://192.168.1.1/desc.xml"): HttpResponse(200, {}, xml)}
    )
    description_cache = DescriptionCache(requester)
    descr_xml = await description_cache.async_get_description_xml(
        "http://192.168.1.1/desc.xml"
    )
    assert descr_xml == xml

    descr_dict = await description_cache.async_get_description_dict(
        "http://192.168.1.1/desc.xml"
    )
    assert descr_dict == {
        "deviceType": "urn:schemas-upnp-org:device:TestDevice:1",
        "UDN": "uuid:test_udn",
        "serialNumber": "ÿÿÿÿ",
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("exc", [asyncio.TimeoutError, aiohttp.ClientError])
async def test_fetch_fail(exc: Exception) -> None:
    """Test fail fetching a description."""
    xml = ""
    requester = UpnpTestRequester(
        {("GET", "http://192.168.1.1/desc.xml"): HttpResponse(200, {}, xml)}
    )
    requester.exceptions.append(exc)
    description_cache = DescriptionCache(requester)
    descr_xml = await description_cache.async_get_description_xml(
        "http://192.168.1.1/desc.xml"
    )
    assert descr_xml is None

    descr_dict = await description_cache.async_get_description_dict(
        "http://192.168.1.1/desc.xml"
    )
    assert descr_dict is None


@pytest.mark.asyncio
async def test_parsing_fail_invalid_xml() -> None:
    """Test fail parsing a description with invalid XML."""
    xml = """<root xmlns="urn:schemas-upnp-org:device-1-0">INVALIDXML"""
    requester = UpnpTestRequester(
        {("GET", "http://192.168.1.1/desc.xml"): HttpResponse(200, {}, xml)}
    )
    description_cache = DescriptionCache(requester)
    descr_xml = await description_cache.async_get_description_xml(
        "http://192.168.1.1/desc.xml"
    )
    assert descr_xml == xml

    descr_dict = await description_cache.async_get_description_dict(
        "http://192.168.1.1/desc.xml"
    )
    assert descr_dict is None


@pytest.mark.asyncio
async def test_parsing_fail_error() -> None:
    """Test fail parsing a description with invalid XML."""
    xml = ""
    requester = UpnpTestRequester(
        {("GET", "http://192.168.1.1/desc.xml"): HttpResponse(200, {}, xml)}
    )
    description_cache = DescriptionCache(requester)
    descr_xml = await description_cache.async_get_description_xml(
        "http://192.168.1.1/desc.xml"
    )
    assert descr_xml == xml

    with patch(
        "async_upnp_client.description_cache.DET.fromstring",
        side_effect=DET.ParseError,
    ):
        descr_dict = await description_cache.async_get_description_dict(
            "http://192.168.1.1/desc.xml"
        )
        assert descr_dict is None
