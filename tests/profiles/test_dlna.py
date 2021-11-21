"""Unit tests for the DLNA profile."""

from typing import List, Sequence

import defusedxml.ElementTree
import pytest
from didl_lite import didl_lite

from async_upnp_client import UpnpEventHandler, UpnpFactory, UpnpStateVariable
from async_upnp_client.client import UpnpService
from async_upnp_client.profiles.dlna import (
    DmrDevice,
    _parse_last_change_event,
    dlna_handle_notify_last_change,
)

from ..conftest import RESPONSE_MAP, UpnpTestNotifyServer, UpnpTestRequester


def assert_xml_equal(
    left: defusedxml.ElementTree, right: defusedxml.ElementTree
) -> None:
    """Check two XML trees are equal."""
    assert left.tag == right.tag
    assert left.text == right.text
    assert left.tail == right.tail
    assert left.attrib == right.attrib
    assert len(left) == len(right)
    for left_child, right_child in zip(left, right):
        assert_xml_equal(left_child, right_child)


def test_parse_last_change_event() -> None:
    """Test parsing a last change event."""
    data = """<Event xmlns="urn:schemas-upnp-org:metadata-1-0/AVT/">
<InstanceID val="0"><TransportState val="PAUSED_PLAYBACK"/></InstanceID>
</Event>"""
    assert _parse_last_change_event(data) == {
        "0": {"TransportState": "PAUSED_PLAYBACK"}
    }


def test_parse_last_change_event_multiple_instances() -> None:
    """Test parsing a last change event with multiple instance."""
    data = """<Event xmlns="urn:schemas-upnp-org:metadata-1-0/AVT/">
<InstanceID val="0"><TransportState val="PAUSED_PLAYBACK"/></InstanceID>
<InstanceID val="1"><TransportState val="PLAYING"/></InstanceID>
</Event>"""
    assert _parse_last_change_event(data) == {
        "0": {"TransportState": "PAUSED_PLAYBACK"},
        "1": {"TransportState": "PLAYING"},
    }


def test_parse_last_change_event_multiple_channels() -> None:
    """Test parsing a last change event with multiple channels."""
    data = """<Event xmlns="urn:schemas-upnp-org:metadata-1-0/AVT/">
<InstanceID val="0">
  <Volume channel="Master" val="10"/>
  <Volume channel="Left" val="20"/>
  <Volume channel="Right" val="30"/>
</InstanceID>
</Event>"""
    assert _parse_last_change_event(data) == {
        "0": {"Volume": "10"},
    }


def test_parse_last_change_event_invalid_xml() -> None:
    """Test parsing an invalid (non valid XML) last change event."""
    data = """<Event xmlns="urn:schemas-upnp-org:metadata-1-0/AVT/">
<InstanceID val="0"><TransportState val="PAUSED_PLAYBACK"></InstanceID>
</Event>"""
    assert _parse_last_change_event(data) == {
        "0": {"TransportState": "PAUSED_PLAYBACK"}
    }


@pytest.mark.asyncio
async def test_on_notify_dlna_event() -> None:
    """Test handling an event.."""
    changed_vars: List[UpnpStateVariable] = []

    def on_event(
        _self: UpnpService, changed_state_variables: Sequence[UpnpStateVariable]
    ) -> None:
        nonlocal changed_vars
        changed_vars += changed_state_variables

        assert changed_state_variables
        if changed_state_variables[0].name == "LastChange":
            last_change = changed_state_variables[0]
            assert last_change.name == "LastChange"

            dlna_handle_notify_last_change(last_change)

    notify_server = UpnpTestNotifyServer()
    requester = UpnpTestRequester(RESPONSE_MAP)
    factory = UpnpFactory(requester)
    device = await factory.async_create_device("http://dlna_dmr:1234/device.xml")
    service = device.service("urn:schemas-upnp-org:service:RenderingControl:1")
    service.on_event = on_event
    event_handler = UpnpEventHandler(notify_server, requester)
    await event_handler.async_subscribe(service)

    headers = {
        "NT": "upnp:event",
        "NTS": "upnp:propchange",
        "SID": "uuid:dummy",
    }
    body = """
<e:propertyset xmlns:e="urn:schemas-upnp-org:event-1-0">
    <e:property>
        <LastChange>
            &lt;Event xmlns=&quot;urn:schemas-upnp-org:metadata-1-0/RCS/&quot;&gt;
                &lt;InstanceID val=&quot;0&quot;&gt;
                    &lt;Mute channel=&quot;Master&quot; val=&quot;0&quot;/&gt;
                    &lt;Volume channel=&quot;Master&quot; val=&quot;50&quot;/&gt;
                    &lt;/InstanceID&gt;
            &lt;/Event&gt;
        </LastChange>
    </e:property>
</e:propertyset>
"""

    result = await event_handler.handle_notify(headers, body)
    assert result == 200

    assert len(changed_vars) == 3

    state_var = service.state_variable("Volume")
    assert state_var.value == 50


@pytest.mark.asyncio
async def test_construct_play_media_metadata_types() -> None:
    """Test various MIME and UPnP type options for construct_play_media_metadata."""
    # pylint: disable=too-many-statements
    notify_server = UpnpTestNotifyServer()
    requester = UpnpTestRequester(RESPONSE_MAP)
    factory = UpnpFactory(requester)
    device = await factory.async_create_device("http://dlna_dmr:1234/device.xml")
    event_handler = UpnpEventHandler(notify_server, requester)
    profile = DmrDevice(device, event_handler=event_handler)

    media_url = "http://dlna_dms:4321/object/file_1222"
    media_title = "Test music"

    # No server to supply DLNA headers
    metadata_xml = await profile.construct_play_media_metadata(media_url, media_title)
    # Sanity check that didl_lite is giving expected XML
    expected_xml = defusedxml.ElementTree.fromstring(
        """<DIDL-Lite xmlns="urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/"
 xmlns:dc="http://purl.org/dc/elements/1.1/"
 xmlns:sec="http://www.sec.co.kr/"
 xmlns:upnp="urn:schemas-upnp-org:metadata-1-0/upnp/">
<item id="0" parentID="-1" restricted="false">
<dc:title>Test music</dc:title>
<upnp:class>object.item</upnp:class>
<res protocolInfo="http-get:*:application/octet-stream:*">
http://dlna_dms:4321/object/file_1222
</res>
</item>
</DIDL-Lite>""".replace(
            "\n", ""
        )
    )
    assert_xml_equal(defusedxml.ElementTree.fromstring(metadata_xml), expected_xml)

    metadata = didl_lite.from_xml_string(metadata_xml)[0]
    assert metadata.title == media_title
    assert metadata.upnp_class == "object.item"
    assert metadata.res
    assert metadata.res is metadata.resources
    assert metadata.res[0].uri == media_url
    assert metadata.res[0].protocol_info == "http-get:*:application/octet-stream:*"

    metadata = didl_lite.from_xml_string(
        await profile.construct_play_media_metadata(media_url + ".mp3", media_title)
    )[0]
    assert metadata.title == media_title
    assert metadata.upnp_class == "object.item.audioItem"
    assert metadata.res[0].uri == media_url + ".mp3"
    assert metadata.res[0].protocol_info == "http-get:*:audio/mpeg:*"

    metadata = didl_lite.from_xml_string(
        await profile.construct_play_media_metadata(
            media_url, media_title, default_mime_type="video/test-mime"
        )
    )[0]
    assert metadata.title == media_title
    assert metadata.upnp_class == "object.item.videoItem"
    assert metadata.res[0].uri == media_url
    assert metadata.res[0].protocol_info == "http-get:*:video/test-mime:*"

    metadata = didl_lite.from_xml_string(
        await profile.construct_play_media_metadata(
            media_url, media_title, default_upnp_class="object.item.imageItem"
        )
    )[0]
    assert metadata.title == media_title
    assert metadata.upnp_class == "object.item.imageItem"
    assert metadata.res[0].uri == media_url
    assert metadata.res[0].protocol_info == "http-get:*:application/octet-stream:*"

    metadata = didl_lite.from_xml_string(
        await profile.construct_play_media_metadata(
            media_url, media_title, override_mime_type="video/test-mime"
        )
    )[0]
    assert metadata.title == media_title
    assert metadata.upnp_class == "object.item.videoItem"
    assert metadata.res[0].uri == media_url
    assert metadata.res[0].protocol_info == "http-get:*:video/test-mime:*"

    metadata = didl_lite.from_xml_string(
        await profile.construct_play_media_metadata(
            media_url, media_title, override_upnp_class="object.item.imageItem"
        )
    )[0]
    assert metadata.title == media_title
    assert metadata.upnp_class == "object.item.imageItem"
    assert metadata.res[0].uri == media_url
    assert metadata.res[0].protocol_info == "http-get:*:application/octet-stream:*"

    metadata = didl_lite.from_xml_string(
        await profile.construct_play_media_metadata(
            media_url,
            media_title,
            override_dlna_features="DLNA_OVERRIDE_FEATURES",
        )
    )[0]
    assert metadata.title == media_title
    assert metadata.upnp_class == "object.item"
    assert metadata.res[0].uri == media_url
    assert (
        metadata.res[0].protocol_info
        == "http-get:*:application/octet-stream:DLNA_OVERRIDE_FEATURES"
    )

    metadata = didl_lite.from_xml_string(
        await profile.construct_play_media_metadata(
            media_url,
            media_title,
            override_mime_type="video/test-mime",
            override_dlna_features="DLNA_OVERRIDE_FEATURES",
        )
    )[0]
    assert metadata.title == media_title
    assert metadata.upnp_class == "object.item.videoItem"
    assert metadata.res[0].uri == media_url
    assert (
        metadata.res[0].protocol_info
        == "http-get:*:video/test-mime:DLNA_OVERRIDE_FEATURES"
    )

    # Media server supplies media information for HEAD requests
    requester.response_map[("HEAD", media_url)] = (
        200,
        {
            "ContentFeatures.dlna.org": "DLNA_SERVER_FEATURES",
            "Content-Type": "video/server-mime",
        },
        "",
    )
    requester.response_map[("HEAD", media_url + ".mp3")] = (
        200,
        {
            "ContentFeatures.dlna.org": "DLNA_SERVER_FEATURES",
            "Content-Type": "video/server-mime",
        },
        "",
    )

    metadata = didl_lite.from_xml_string(
        await profile.construct_play_media_metadata(media_url, media_title)
    )[0]
    assert metadata.title == media_title
    assert metadata.upnp_class == "object.item.videoItem"
    assert metadata.res[0].uri == media_url
    assert (
        metadata.res[0].protocol_info
        == "http-get:*:video/server-mime:DLNA_SERVER_FEATURES"
    )

    metadata = didl_lite.from_xml_string(
        await profile.construct_play_media_metadata(media_url + ".mp3", media_title)
    )[0]
    assert metadata.title == media_title
    assert metadata.upnp_class == "object.item.videoItem"
    assert metadata.res[0].uri == media_url + ".mp3"
    assert (
        metadata.res[0].protocol_info
        == "http-get:*:video/server-mime:DLNA_SERVER_FEATURES"
    )

    metadata = didl_lite.from_xml_string(
        await profile.construct_play_media_metadata(
            media_url, media_title, default_mime_type="video/test-mime"
        )
    )[0]
    assert metadata.title == media_title
    assert metadata.upnp_class == "object.item.videoItem"
    assert metadata.res[0].uri == media_url
    assert (
        metadata.res[0].protocol_info
        == "http-get:*:video/server-mime:DLNA_SERVER_FEATURES"
    )

    metadata = didl_lite.from_xml_string(
        await profile.construct_play_media_metadata(
            media_url, media_title, default_upnp_class="object.item.imageItem"
        )
    )[0]
    assert metadata.title == media_title
    assert metadata.upnp_class == "object.item.videoItem"
    assert metadata.res[0].uri == media_url
    assert (
        metadata.res[0].protocol_info
        == "http-get:*:video/server-mime:DLNA_SERVER_FEATURES"
    )

    metadata = didl_lite.from_xml_string(
        await profile.construct_play_media_metadata(
            media_url, media_title, override_mime_type="image/test-mime"
        )
    )[0]
    assert metadata.title == media_title
    assert metadata.upnp_class == "object.item.imageItem"
    assert metadata.res[0].uri == media_url
    assert (
        metadata.res[0].protocol_info
        == "http-get:*:image/test-mime:DLNA_SERVER_FEATURES"
    )

    metadata = didl_lite.from_xml_string(
        await profile.construct_play_media_metadata(
            media_url, media_title, override_upnp_class="object.item.imageItem"
        )
    )[0]
    assert metadata.title == media_title
    assert metadata.upnp_class == "object.item.imageItem"
    assert metadata.res[0].uri == media_url
    assert (
        metadata.res[0].protocol_info
        == "http-get:*:video/server-mime:DLNA_SERVER_FEATURES"
    )

    metadata = didl_lite.from_xml_string(
        await profile.construct_play_media_metadata(
            media_url,
            media_title,
            override_dlna_features="DLNA_OVERRIDE_FEATURES",
        )
    )[0]
    assert metadata.title == media_title
    assert metadata.upnp_class == "object.item.videoItem"
    assert metadata.res[0].uri == media_url
    assert (
        metadata.res[0].protocol_info
        == "http-get:*:video/server-mime:DLNA_OVERRIDE_FEATURES"
    )

    metadata = didl_lite.from_xml_string(
        await profile.construct_play_media_metadata(
            media_url,
            media_title,
            override_mime_type="image/test-mime",
            override_dlna_features="DLNA_OVERRIDE_FEATURES",
        )
    )[0]
    assert metadata.title == media_title
    assert metadata.upnp_class == "object.item.imageItem"
    assert metadata.res[0].uri == media_url
    assert (
        metadata.res[0].protocol_info
        == "http-get:*:image/test-mime:DLNA_OVERRIDE_FEATURES"
    )


@pytest.mark.asyncio
async def test_construct_play_media_metadata_meta_data() -> None:
    """Test meta_data values for construct_play_media_metadata."""
    notify_server = UpnpTestNotifyServer()
    requester = UpnpTestRequester(RESPONSE_MAP)
    factory = UpnpFactory(requester)
    device = await factory.async_create_device("http://dlna_dmr:1234/device.xml")
    event_handler = UpnpEventHandler(notify_server, requester)
    profile = DmrDevice(device, event_handler=event_handler)

    media_url = "http://dlna_dms:4321/object/file_1222.mp3"
    media_title = "Test music"
    meta_data = {
        "title": "Test override title",  # Should override media_title parameter
        "description": "Short test description",  # In base audioItem class
        "artist": "Test singer",
        "album": "Test album",
        "originalTrackNumber": 3,  # Should be converted to lower_camel_case
    }

    # No server information about media type or contents

    # Without specifying UPnP class, only generic types lacking certain values are used
    metadata = didl_lite.from_xml_string(
        await profile.construct_play_media_metadata(
            media_url,
            media_title,
            meta_data=meta_data,
        )
    )[0]
    assert metadata.upnp_class == "object.item.audioItem"
    assert metadata.title == "Test override title"
    assert metadata.description == "Short test description"
    assert not hasattr(metadata, "artist")
    assert not hasattr(metadata, "album")
    assert not hasattr(metadata, "original_track_number")
    assert metadata.res[0].uri == media_url
    assert metadata.res[0].protocol_info == "http-get:*:audio/mpeg:*"

    # Set the UPnP class correctly
    metadata = didl_lite.from_xml_string(
        await profile.construct_play_media_metadata(
            media_url,
            media_title,
            override_upnp_class="object.item.audioItem.musicTrack",
            meta_data=meta_data,
        )
    )[0]
    assert metadata.upnp_class == "object.item.audioItem.musicTrack"
    assert metadata.title == "Test override title"
    assert metadata.description == "Short test description"
    assert metadata.artist == "Test singer"
    assert metadata.album == "Test album"
    assert metadata.original_track_number == "3"
    assert metadata.res[0].uri == media_url
    assert metadata.res[0].protocol_info == "http-get:*:audio/mpeg:*"
