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
    requester = UpnpTestRequester({("GET", "http://192.168.1.1/desc.xml"): HttpResponse(200, {}, xml)})
    description_cache = DescriptionCache(requester)
    descr_xml = await description_cache.async_get_description_xml("http://192.168.1.1/desc.xml")
    assert descr_xml == xml

    descr_dict = await description_cache.async_get_description_dict("http://192.168.1.1/desc.xml")
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
    requester = UpnpTestRequester({("GET", "http://192.168.1.1/desc.xml"): HttpResponse(200, {}, xml)})
    description_cache = DescriptionCache(requester)
    descr_xml = await description_cache.async_get_description_xml("http://192.168.1.1/desc.xml")
    assert descr_xml == xml

    descr_dict = await description_cache.async_get_description_dict("http://192.168.1.1/desc.xml")
    assert descr_dict == {
        "deviceType": "urn:schemas-upnp-org:device:TestDevice:1",
        "UDN": "uuid:test_udn",
        "serialNumber": "ÿÿÿÿ",
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("exc", [TimeoutError, aiohttp.ClientError])
async def test_fetch_fail(exc: Exception) -> None:
    """Test fail fetching a description."""
    xml = ""
    requester = UpnpTestRequester({("GET", "http://192.168.1.1/desc.xml"): HttpResponse(200, {}, xml)})
    requester.exceptions.append(exc)
    description_cache = DescriptionCache(requester)
    descr_xml = await description_cache.async_get_description_xml("http://192.168.1.1/desc.xml")
    assert descr_xml is None

    descr_dict = await description_cache.async_get_description_dict("http://192.168.1.1/desc.xml")
    assert descr_dict is None


@pytest.mark.asyncio
async def test_parsing_fail_invalid_xml() -> None:
    """Test fail parsing a description with invalid XML."""
    xml = """<root xmlns="urn:schemas-upnp-org:device-1-0">INVALIDXML"""
    requester = UpnpTestRequester({("GET", "http://192.168.1.1/desc.xml"): HttpResponse(200, {}, xml)})
    description_cache = DescriptionCache(requester)
    descr_xml = await description_cache.async_get_description_xml("http://192.168.1.1/desc.xml")
    assert descr_xml == xml

    descr_dict = await description_cache.async_get_description_dict("http://192.168.1.1/desc.xml")
    assert descr_dict is None


@pytest.mark.asyncio
async def test_parsing_fail_error() -> None:
    """Test fail parsing a description with invalid XML."""
    xml = ""
    requester = UpnpTestRequester({("GET", "http://192.168.1.1/desc.xml"): HttpResponse(200, {}, xml)})
    description_cache = DescriptionCache(requester)
    descr_xml = await description_cache.async_get_description_xml("http://192.168.1.1/desc.xml")
    assert descr_xml == xml

    with patch(
        "async_upnp_client.description_cache.DET.fromstring",
        side_effect=DET.ParseError,
    ):
        descr_dict = await description_cache.async_get_description_dict("http://192.168.1.1/desc.xml")
        assert descr_dict is None


@pytest.mark.asyncio
async def test_parsing_deeply_nested_no_deadlock() -> None:
    """Test a deeply nested description does not raise or deadlock the cache.

    Regression test for GHSA-3w9h-mmq8-jq86: a well-formed but deeply nested
    document made etree_to_dict() raise RecursionError, which escaped and left
    the location cached as an unset Event, deadlocking every later lookup.
    """
    depth = 2000
    xml = "<root>" + "<a>" * depth + "x" + "</a>" * depth + "</root>"
    requester = UpnpTestRequester({("GET", "http://192.168.1.1/desc.xml"): HttpResponse(200, {}, xml)})
    description_cache = DescriptionCache(requester)

    # First lookup must return None rather than propagating RecursionError.
    descr_dict = await asyncio.wait_for(
        description_cache.async_get_description_dict("http://192.168.1.1/desc.xml"),
        timeout=5,
    )
    assert descr_dict is None

    # Second lookup of the same location must not deadlock on a stranded Event.
    descr_dict = await asyncio.wait_for(
        description_cache.async_get_description_dict("http://192.168.1.1/desc.xml"),
        timeout=5,
    )
    assert descr_dict is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "xml",
    [
        "<root>text</root>",
        "<root/>",
    ],
)
async def test_parsing_unexpected_shape_returns_none(xml: str) -> None:
    """Test well-formed XML with an unexpected shape returns None, no deadlock."""
    requester = UpnpTestRequester({("GET", "http://192.168.1.1/desc.xml"): HttpResponse(200, {}, xml)})
    description_cache = DescriptionCache(requester)

    descr_dict = await asyncio.wait_for(
        description_cache.async_get_description_dict("http://192.168.1.1/desc.xml"),
        timeout=5,
    )
    assert descr_dict is None

    descr_dict = await asyncio.wait_for(
        description_cache.async_get_description_dict("http://192.168.1.1/desc.xml"),
        timeout=5,
    )
    assert descr_dict is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "xml",
    [
        '<!DOCTYPE root [<!ENTITY a "x">]><root>&a;</root>',
        '<!DOCTYPE root [<!ENTITY a SYSTEM "file:///etc/hostname">]><root>&a;</root>',
        "<root>\ud800</root>",  # Lone surrogate, e.g. from a UTF-7 body.
    ],
)
async def test_parsing_rejected_returns_none(xml: str) -> None:
    """Test documents the parser rejects return None, no deadlock."""
    requester = UpnpTestRequester({("GET", "http://192.168.1.1/desc.xml"): HttpResponse(200, {}, xml)})
    description_cache = DescriptionCache(requester)

    descr_dict = await asyncio.wait_for(
        description_cache.async_get_description_dict("http://192.168.1.1/desc.xml"),
        timeout=5,
    )
    assert descr_dict is None

    descr_dict = await asyncio.wait_for(
        description_cache.async_get_description_dict("http://192.168.1.1/desc.xml"),
        timeout=5,
    )
    assert descr_dict is None


@pytest.mark.asyncio
async def test_convert_recursion_error_no_deadlock() -> None:
    """Test a RecursionError while converting does not strand the cache Event."""
    xml = """<root xmlns="urn:schemas-upnp-org:device-1-0">
  <device>
    <deviceType>urn:schemas-upnp-org:device:TestDevice:1</deviceType>
  </device>
</root>"""
    requester = UpnpTestRequester({("GET", "http://192.168.1.1/desc.xml"): HttpResponse(200, {}, xml)})
    description_cache = DescriptionCache(requester)

    with patch(
        "async_upnp_client.description_cache.etree_to_dict",
        side_effect=RecursionError,
    ):
        descr_dict = await asyncio.wait_for(
            description_cache.async_get_description_dict("http://192.168.1.1/desc.xml"),
            timeout=5,
        )
        assert descr_dict is None

    # The location must not be stranded as an unset Event after the error.
    descr_dict = await asyncio.wait_for(
        description_cache.async_get_description_dict("http://192.168.1.1/desc.xml"),
        timeout=5,
    )
    assert descr_dict is None


@pytest.mark.asyncio
async def test_unhandled_error_no_deadlock() -> None:
    """Test an error escaping the conversion still releases the cache Event."""
    xml = "<root/>"
    requester = UpnpTestRequester({("GET", "http://192.168.1.1/desc.xml"): HttpResponse(200, {}, xml)})
    description_cache = DescriptionCache(requester)

    with patch(
        "async_upnp_client.description_cache._description_xml_to_dict",
        side_effect=RuntimeError,
    ):
        with pytest.raises(RuntimeError):
            await asyncio.wait_for(
                description_cache.async_get_description_dict("http://192.168.1.1/desc.xml"),
                timeout=5,
            )

    descr_dict = await asyncio.wait_for(
        description_cache.async_get_description_dict("http://192.168.1.1/desc.xml"),
        timeout=5,
    )
    assert descr_dict is None


@pytest.mark.asyncio
@pytest.mark.parametrize("refetch_before_waiter_wakes", [False, True])
async def test_cancelled_fetch_not_cached(refetch_before_waiter_wakes: bool) -> None:
    """Test a cancelled fetch releases its waiter and is retried, not cached."""
    xml = """<root xmlns="urn:schemas-upnp-org:device-1-0">
  <device>
    <deviceType>urn:schemas-upnp-org:device:TestDevice:1</deviceType>
  </device>
</root>"""
    requester = UpnpTestRequester({("GET", "http://192.168.1.1/desc.xml"): HttpResponse(200, {}, xml)})
    description_cache = DescriptionCache(requester)
    expected = {"deviceType": "urn:schemas-upnp-org:device:TestDevice:1"}

    owner = asyncio.create_task(description_cache.async_get_description_dict("http://192.168.1.1/desc.xml"))
    await asyncio.sleep(0)  # Owner caches its Event and starts fetching.
    waiter = asyncio.create_task(description_cache.async_get_description_dict("http://192.168.1.1/desc.xml"))
    await asyncio.sleep(0)  # Waiter awaits the owner's Event.

    owner.cancel()
    refetch = None
    if refetch_before_waiter_wakes:
        # Runs after the owner handles the cancellation but before the waiter
        # wakes, so the waiter finds this new fetch's Event in the cache.
        refetch = asyncio.create_task(description_cache.async_get_description_dict("http://192.168.1.1/desc.xml"))
    with pytest.raises(asyncio.CancelledError):
        await owner

    assert await asyncio.wait_for(waiter, timeout=5) is None
    if refetch is not None:
        assert await asyncio.wait_for(refetch, timeout=5) == expected

    descr_dict = await asyncio.wait_for(
        description_cache.async_get_description_dict("http://192.168.1.1/desc.xml"),
        timeout=5,
    )
    assert descr_dict == expected
