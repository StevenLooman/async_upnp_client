"""Unit tests for the DLNA profile."""

from typing import List, Sequence

from didl_lite import didl_lite
import pytest

from async_upnp_client import UpnpEventHandler, UpnpFactory, UpnpStateVariable
from async_upnp_client.client import UpnpService
from async_upnp_client.profiles.dlna import (
    _parse_last_change_event,
    dlna_handle_notify_last_change,
    DmrDevice,
)

from ..upnp_test_requester import RESPONSE_MAP, UpnpTestRequester


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

    requester = UpnpTestRequester(RESPONSE_MAP)
    factory = UpnpFactory(requester)
    device = await factory.async_create_device("http://dlna_dmr:1234/device.xml")
    service = device.service("urn:schemas-upnp-org:service:RenderingControl:1")
    service.on_event = on_event
    event_handler = UpnpEventHandler("http://localhost:11302", requester)
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
    requester = UpnpTestRequester(RESPONSE_MAP)
    factory = UpnpFactory(requester)
    device = await factory.async_create_device("http://dlna_dmr:1234/device.xml")
    event_handler = UpnpEventHandler("http://localhost:11302", requester)
    profile = DmrDevice(device, event_handler=event_handler)

    MEDIA_URL = "http://dlna_dms:4321/object/file_1222"
    MEDIA_TITLE = "Test music"

    # No server to supply DLNA headers
    metadata = didl_lite.from_xml_string(
        await profile.construct_play_media_metadata(MEDIA_URL, MEDIA_TITLE)
    )[0]
    assert metadata.title == MEDIA_TITLE
    assert metadata.upnp_class == "object.item"
    assert metadata.res[0].uri == MEDIA_URL
    assert metadata.res[0].protocol_info == "http-get:*:application/octet-stream:*"

    metadata = didl_lite.from_xml_string(
        await profile.construct_play_media_metadata(MEDIA_URL + ".mp3", MEDIA_TITLE)
    )[0]
    assert metadata.title == MEDIA_TITLE
    assert metadata.upnp_class == "object.item.audioItem"
    assert metadata.res[0].uri == MEDIA_URL + ".mp3"
    assert metadata.res[0].protocol_info == "http-get:*:audio/mpeg:*"

    metadata = didl_lite.from_xml_string(
        await profile.construct_play_media_metadata(
            MEDIA_URL, MEDIA_TITLE, default_mime_type="video/test-mime"
        )
    )[0]
    assert metadata.title == MEDIA_TITLE
    assert metadata.upnp_class == "object.item.videoItem"
    assert metadata.res[0].uri == MEDIA_URL
    assert metadata.res[0].protocol_info == "http-get:*:video/test-mime:*"

    metadata = didl_lite.from_xml_string(
        await profile.construct_play_media_metadata(
            MEDIA_URL, MEDIA_TITLE, default_upnp_class="object.item.imageItem"
        )
    )[0]
    assert metadata.title == MEDIA_TITLE
    assert metadata.upnp_class == "object.item.imageItem"
    assert metadata.res[0].uri == MEDIA_URL
    assert metadata.res[0].protocol_info == "http-get:*:application/octet-stream:*"

    metadata = didl_lite.from_xml_string(
        await profile.construct_play_media_metadata(
            MEDIA_URL, MEDIA_TITLE, override_mime_type="video/test-mime"
        )
    )[0]
    assert metadata.title == MEDIA_TITLE
    assert metadata.upnp_class == "object.item.videoItem"
    assert metadata.res[0].uri == MEDIA_URL
    assert metadata.res[0].protocol_info == "http-get:*:video/test-mime:*"

    metadata = didl_lite.from_xml_string(
        await profile.construct_play_media_metadata(
            MEDIA_URL, MEDIA_TITLE, override_upnp_class="object.item.imageItem"
        )
    )[0]
    assert metadata.title == MEDIA_TITLE
    assert metadata.upnp_class == "object.item.imageItem"
    assert metadata.res[0].uri == MEDIA_URL
    assert metadata.res[0].protocol_info == "http-get:*:application/octet-stream:*"

    metadata = didl_lite.from_xml_string(
        await profile.construct_play_media_metadata(
            MEDIA_URL,
            MEDIA_TITLE,
            override_dlna_features="DLNA_OVERRIDE_FEATURES",
        )
    )[0]
    assert metadata.title == MEDIA_TITLE
    assert metadata.upnp_class == "object.item"
    assert metadata.res[0].uri == MEDIA_URL
    assert (
        metadata.res[0].protocol_info
        == "http-get:*:application/octet-stream:DLNA_OVERRIDE_FEATURES"
    )

    metadata = didl_lite.from_xml_string(
        await profile.construct_play_media_metadata(
            MEDIA_URL,
            MEDIA_TITLE,
            override_mime_type="video/test-mime",
            override_dlna_features="DLNA_OVERRIDE_FEATURES",
        )
    )[0]
    assert metadata.title == MEDIA_TITLE
    assert metadata.upnp_class == "object.item.videoItem"
    assert metadata.res[0].uri == MEDIA_URL
    assert (
        metadata.res[0].protocol_info
        == "http-get:*:video/test-mime:DLNA_OVERRIDE_FEATURES"
    )

    # Media server supplies media information for HEAD requests
    requester.response_map[("HEAD", MEDIA_URL)] = (
        200,
        {
            "ContentFeatures.dlna.org": "DLNA_SERVER_FEATURES",
            "Content-Type": "video/server-mime",
        },
        "",
    )
    requester.response_map[("HEAD", MEDIA_URL + ".mp3")] = (
        200,
        {
            "ContentFeatures.dlna.org": "DLNA_SERVER_FEATURES",
            "Content-Type": "video/server-mime",
        },
        "",
    )

    metadata = didl_lite.from_xml_string(
        await profile.construct_play_media_metadata(MEDIA_URL, MEDIA_TITLE)
    )[0]
    assert metadata.title == MEDIA_TITLE
    assert metadata.upnp_class == "object.item.videoItem"
    assert metadata.res[0].uri == MEDIA_URL
    assert (
        metadata.res[0].protocol_info
        == "http-get:*:video/server-mime:DLNA_SERVER_FEATURES"
    )

    metadata = didl_lite.from_xml_string(
        await profile.construct_play_media_metadata(MEDIA_URL + ".mp3", MEDIA_TITLE)
    )[0]
    assert metadata.title == MEDIA_TITLE
    assert metadata.upnp_class == "object.item.videoItem"
    assert metadata.res[0].uri == MEDIA_URL + ".mp3"
    assert (
        metadata.res[0].protocol_info
        == "http-get:*:video/server-mime:DLNA_SERVER_FEATURES"
    )

    metadata = didl_lite.from_xml_string(
        await profile.construct_play_media_metadata(
            MEDIA_URL, MEDIA_TITLE, default_mime_type="video/test-mime"
        )
    )[0]
    assert metadata.title == MEDIA_TITLE
    assert metadata.upnp_class == "object.item.videoItem"
    assert metadata.res[0].uri == MEDIA_URL
    assert (
        metadata.res[0].protocol_info
        == "http-get:*:video/server-mime:DLNA_SERVER_FEATURES"
    )

    metadata = didl_lite.from_xml_string(
        await profile.construct_play_media_metadata(
            MEDIA_URL, MEDIA_TITLE, default_upnp_class="object.item.imageItem"
        )
    )[0]
    assert metadata.title == MEDIA_TITLE
    assert metadata.upnp_class == "object.item.videoItem"
    assert metadata.res[0].uri == MEDIA_URL
    assert (
        metadata.res[0].protocol_info
        == "http-get:*:video/server-mime:DLNA_SERVER_FEATURES"
    )

    metadata = didl_lite.from_xml_string(
        await profile.construct_play_media_metadata(
            MEDIA_URL, MEDIA_TITLE, override_mime_type="image/test-mime"
        )
    )[0]
    assert metadata.title == MEDIA_TITLE
    assert metadata.upnp_class == "object.item.imageItem"
    assert metadata.res[0].uri == MEDIA_URL
    assert (
        metadata.res[0].protocol_info
        == "http-get:*:image/test-mime:DLNA_SERVER_FEATURES"
    )

    metadata = didl_lite.from_xml_string(
        await profile.construct_play_media_metadata(
            MEDIA_URL, MEDIA_TITLE, override_upnp_class="object.item.imageItem"
        )
    )[0]
    assert metadata.title == MEDIA_TITLE
    assert metadata.upnp_class == "object.item.imageItem"
    assert metadata.res[0].uri == MEDIA_URL
    assert (
        metadata.res[0].protocol_info
        == "http-get:*:video/server-mime:DLNA_SERVER_FEATURES"
    )

    metadata = didl_lite.from_xml_string(
        await profile.construct_play_media_metadata(
            MEDIA_URL,
            MEDIA_TITLE,
            override_dlna_features="DLNA_OVERRIDE_FEATURES",
        )
    )[0]
    assert metadata.title == MEDIA_TITLE
    assert metadata.upnp_class == "object.item.videoItem"
    assert metadata.res[0].uri == MEDIA_URL
    assert (
        metadata.res[0].protocol_info
        == "http-get:*:video/server-mime:DLNA_OVERRIDE_FEATURES"
    )

    metadata = didl_lite.from_xml_string(
        await profile.construct_play_media_metadata(
            MEDIA_URL,
            MEDIA_TITLE,
            override_mime_type="image/test-mime",
            override_dlna_features="DLNA_OVERRIDE_FEATURES",
        )
    )[0]
    assert metadata.title == MEDIA_TITLE
    assert metadata.upnp_class == "object.item.imageItem"
    assert metadata.res[0].uri == MEDIA_URL
    assert (
        metadata.res[0].protocol_info
        == "http-get:*:image/test-mime:DLNA_OVERRIDE_FEATURES"
    )


@pytest.mark.asyncio
async def test_construct_play_media_metadata_meta_data() -> None:
    """Test meta_data values for construct_play_media_metadata."""
    requester = UpnpTestRequester(RESPONSE_MAP)
    factory = UpnpFactory(requester)
    device = await factory.async_create_device("http://dlna_dmr:1234/device.xml")
    event_handler = UpnpEventHandler("http://localhost:11302", requester)
    profile = DmrDevice(device, event_handler=event_handler)

    MEDIA_URL = "http://dlna_dms:4321/object/file_1222.mp3"
    MEDIA_TITLE = "Test music"
    META_DATA = {
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
            MEDIA_URL,
            MEDIA_TITLE,
            meta_data=META_DATA,
        )
    )[0]
    assert metadata.upnp_class == "object.item.audioItem"
    assert metadata.title == "Test override title"
    assert metadata.description == "Short test description"
    assert not hasattr(metadata, "artist")
    assert not hasattr(metadata, "album")
    assert not hasattr(metadata, "original_track_number")
    assert metadata.res[0].uri == MEDIA_URL
    assert metadata.res[0].protocol_info == "http-get:*:audio/mpeg:*"

    # Set the UPnP class correctly
    metadata = didl_lite.from_xml_string(
        await profile.construct_play_media_metadata(
            MEDIA_URL,
            MEDIA_TITLE,
            override_upnp_class="object.item.audioItem.musicTrack",
            meta_data=META_DATA,
        )
    )[0]
    assert metadata.upnp_class == "object.item.audioItem.musicTrack"
    assert metadata.title == "Test override title"
    assert metadata.description == "Short test description"
    assert metadata.artist == "Test singer"
    assert metadata.album == "Test album"
    assert metadata.original_track_number == "3"
    assert metadata.res[0].uri == MEDIA_URL
    assert metadata.res[0].protocol_info == "http-get:*:audio/mpeg:*"
