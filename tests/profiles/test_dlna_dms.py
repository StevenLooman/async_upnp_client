"""Unit tests for the DLNA DMS profile."""

import pytest

from async_upnp_client import UpnpFactory
from async_upnp_client.exceptions import UpnpResponseError
from async_upnp_client.profiles.dlna import DmsDevice

from ..conftest import RESPONSE_MAP, UpnpTestNotifyServer, UpnpTestRequester, read_file


@pytest.mark.asyncio
async def test_async_browse_metadata() -> None:
    """Test retrieving object metadata."""
    requester = UpnpTestRequester(RESPONSE_MAP)
    factory = UpnpFactory(requester)
    device = await factory.async_create_device("http://dlna_dms:1234/device.xml")
    notify_server = UpnpTestNotifyServer(
        requester=requester,
        source=("192.168.1.2", 8090),
    )
    event_handler = notify_server.event_handler
    profile = DmsDevice(device, event_handler=event_handler)

    # Object 0 is the root and must always exist
    requester.response_map[("POST", "http://dlna_dms:1234/upnp/control/ContentDir")] = (
        200,
        {},
        read_file("dlna/dms/action_Browse_metadata_0.xml"),
    )
    metadata = await profile.async_browse_metadata("0")
    assert metadata.parent_id == "-1"
    assert metadata.id == "0"
    assert metadata.title == "root"
    assert metadata.upnp_class == "object.container.storageFolder"
    assert metadata.child_count == "4"

    # Object 2 will give some different results
    requester.response_map[("POST", "http://dlna_dms:1234/upnp/control/ContentDir")] = (
        200,
        {},
        read_file("dlna/dms/action_Browse_metadata_2.xml"),
    )
    metadata = await profile.async_browse_metadata("2")
    assert metadata.parent_id == "0"
    assert metadata.id == "2"
    assert metadata.title == "Video"
    assert metadata.upnp_class == "object.container.storageFolder"
    assert metadata.child_count == "3"

    # Object that is an item and not a container
    requester.response_map[("POST", "http://dlna_dms:1234/upnp/control/ContentDir")] = (
        200,
        {},
        read_file("dlna/dms/action_Browse_metadata_item.xml"),
    )
    metadata = await profile.async_browse_metadata("1$6$35$1$1")
    assert metadata.parent_id == "1$6$35$1"
    assert metadata.id == "1$6$35$1$1"
    assert metadata.title == "Test song"
    assert metadata.upnp_class == "object.item.audioItem.musicTrack"
    assert metadata.artist == "Test artist"
    assert metadata.genre == "Rock & Roll"
    assert len(metadata.resources) == 1
    assert metadata.resources[0].uri == "http://dlna_dms:1234/media/2483.mp3"
    assert (
        metadata.resources[0].protocol_info
        == "http-get:*:audio/mpeg:DLNA.ORG_PN=MP3;DLNA.ORG_OP=01;DLNA.ORG_CI=0;"
        "DLNA.ORG_FLAGS=01700000000000000000000000000000"
    )
    assert metadata.resources[0].size == "2905191"
    assert metadata.resources[0].duration == "0:02:00.938"

    # Bad object ID should result in a UpnpError (HTTP 701: No such object)
    requester.exceptions.append(UpnpResponseError(status=701))
    with pytest.raises(UpnpResponseError) as err:
        await profile.async_browse_metadata("no object")

    assert err.value.status == 701


@pytest.mark.asyncio
async def test_async_browse_children() -> None:
    """Test retrieving children of a container."""
    # pylint: disable=too-many-statements
    requester = UpnpTestRequester(RESPONSE_MAP)
    factory = UpnpFactory(requester)
    device = await factory.async_create_device("http://dlna_dms:1234/device.xml")
    notify_server = UpnpTestNotifyServer(
        requester=requester,
        source=("192.168.1.2", 8090),
    )
    event_handler = notify_server.event_handler
    profile = DmsDevice(device, event_handler=event_handler)

    # Object 0 is the root and must always exist
    requester.response_map[("POST", "http://dlna_dms:1234/upnp/control/ContentDir")] = (
        200,
        {},
        read_file("dlna/dms/action_Browse_children_0.xml"),
    )
    result = await profile.async_browse_direct_children("0")
    assert result.number_returned == 4
    assert result.total_matches == 4
    assert result.update_id == 2333
    children = result.result
    assert len(children) == 4
    assert children[0].title == "Browse Folders"
    assert children[0].id == "64"
    assert children[0].child_count == "4"
    assert children[1].title == "Music"
    assert children[1].id == "1"
    assert children[1].child_count == "7"
    assert children[2].title == "Pictures"
    assert children[2].id == "3"
    assert children[2].child_count == "5"
    assert children[3].title == "Video"
    assert children[3].id == "2"
    assert children[3].child_count == "3"

    # Object 2 will give some different results
    requester.response_map[("POST", "http://dlna_dms:1234/upnp/control/ContentDir")] = (
        200,
        {},
        read_file("dlna/dms/action_Browse_children_2.xml"),
    )
    result = await profile.async_browse_direct_children("2")
    assert result.number_returned == 3
    assert result.total_matches == 3
    assert result.update_id == 2333
    children = result.result
    assert len(children) == 3
    assert children[0].title == "All Video"
    assert children[0].id == "2$8"
    assert children[0].child_count == "583"
    assert children[1].title == "Folders"
    assert children[1].id == "2$15"
    assert children[1].child_count == "2"
    assert children[2].title == "Recently Added"
    assert children[2].id == "2$FF0"
    assert children[2].child_count == "50"

    # Object that is an item and not a container
    requester.response_map[("POST", "http://dlna_dms:1234/upnp/control/ContentDir")] = (
        200,
        {},
        read_file("dlna/dms/action_Browse_children_item.xml"),
    )
    result = await profile.async_browse_direct_children("1$6$35$1$1")
    assert result.number_returned == 0
    assert result.total_matches == 0
    assert result.update_id == 2333
    assert result.result == []

    # Bad object ID should result in a UpnpError (HTTP 701: No such object)
    requester.exceptions.append(UpnpResponseError(status=701))
    with pytest.raises(UpnpResponseError) as err:
        await profile.async_browse_direct_children("no object")

    assert err.value.status == 701
