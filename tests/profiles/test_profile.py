"""Unit tests for profile."""
# pylint: disable=protected-access

import asyncio
import time
from datetime import timedelta
from unittest.mock import Mock

import pytest

from async_upnp_client import UpnpFactory
from async_upnp_client.exceptions import (
    UpnpCommunicationError,
    UpnpConnectionError,
    UpnpResponseError,
)
from async_upnp_client.profiles.dlna import DmrDevice
from async_upnp_client.profiles.igd import IgdDevice

from ..conftest import RESPONSE_MAP, UpnpTestNotifyServer, UpnpTestRequester, read_file


class TestUpnpProfileDevice:
    """Test UPnpProfileDevice."""

    # pylint: disable=no-self-use

    @pytest.mark.asyncio
    async def test_action_exists(self) -> None:
        """Test getting existing action."""
        requester = UpnpTestRequester(RESPONSE_MAP)
        factory = UpnpFactory(requester)
        device = await factory.async_create_device("http://dlna_dmr:1234/device.xml")
        notify_server = UpnpTestNotifyServer(
            requester=requester,
            source=("192.168.1.2", 8090),
        )
        event_handler = notify_server.event_handler
        profile = DmrDevice(device, event_handler=event_handler)

        # doesn't error
        assert profile._action("RC", "GetMute") is not None

    @pytest.mark.asyncio
    async def test_action_not_exists(self) -> None:
        """Test getting non-existing action."""
        requester = UpnpTestRequester(RESPONSE_MAP)
        factory = UpnpFactory(requester)
        device = await factory.async_create_device("http://dlna_dmr:1234/device.xml")
        notify_server = UpnpTestNotifyServer(
            requester=requester,
            source=("192.168.1.2", 8090),
        )
        event_handler = notify_server.event_handler
        profile = DmrDevice(device, event_handler=event_handler)

        # doesn't error
        assert profile._action("RC", "NonExisting") is None

    @pytest.mark.asyncio
    async def test_icon(self) -> None:
        """Test getting an icon returns the best available."""
        requester = UpnpTestRequester(RESPONSE_MAP)
        factory = UpnpFactory(requester)
        device = await factory.async_create_device("http://dlna_dmr:1234/device.xml")
        notify_server = UpnpTestNotifyServer(
            requester=requester,
            source=("192.168.1.2", 8090),
        )
        event_handler = notify_server.event_handler
        profile = DmrDevice(device, event_handler=event_handler)

        assert profile.icon == "http://dlna_dmr:1234/device_icon_120.png"

    @pytest.mark.asyncio
    async def test_is_profile_device(self) -> None:
        """Test is_profile_device works for root and embedded devices."""
        requester = UpnpTestRequester(RESPONSE_MAP)
        factory = UpnpFactory(requester)
        device = await factory.async_create_device("http://dlna_dmr:1234/device.xml")
        embedded = await factory.async_create_device(
            "http://dlna_dmr:1234/device_embedded.xml"
        )
        no_services = await factory.async_create_device(
            "http://dlna_dmr:1234/device_incomplete.xml"
        )
        empty_descriptor = await factory.async_create_device(
            "http://dlna_dmr:1234/device_with_empty_descriptor.xml"
        )
        igd_device = await factory.async_create_device("http://igd:1234/device.xml")

        assert DmrDevice.is_profile_device(device) is True
        assert DmrDevice.is_profile_device(embedded) is True
        assert DmrDevice.is_profile_device(no_services) is False
        assert DmrDevice.is_profile_device(igd_device) is False

        assert IgdDevice.is_profile_device(device) is False
        assert IgdDevice.is_profile_device(embedded) is False
        assert IgdDevice.is_profile_device(no_services) is False
        assert IgdDevice.is_profile_device(empty_descriptor) is False
        assert IgdDevice.is_profile_device(igd_device) is True

    @pytest.mark.asyncio
    async def test_is_profile_device_non_strict(self) -> None:
        """Test is_profile_device works for root and embedded devices."""
        requester = UpnpTestRequester(RESPONSE_MAP)
        factory = UpnpFactory(requester, non_strict=True)
        device = await factory.async_create_device("http://dlna_dmr:1234/device.xml")
        embedded = await factory.async_create_device(
            "http://dlna_dmr:1234/device_embedded.xml"
        )
        no_services = await factory.async_create_device(
            "http://dlna_dmr:1234/device_incomplete.xml"
        )
        empty_descriptor = await factory.async_create_device(
            "http://dlna_dmr:1234/device_with_empty_descriptor.xml"
        )
        igd_device = await factory.async_create_device("http://igd:1234/device.xml")

        assert DmrDevice.is_profile_device(device) is True
        assert DmrDevice.is_profile_device(embedded) is True
        assert DmrDevice.is_profile_device(no_services) is False
        assert DmrDevice.is_profile_device(igd_device) is False

        assert IgdDevice.is_profile_device(device) is False
        assert IgdDevice.is_profile_device(embedded) is False
        assert IgdDevice.is_profile_device(no_services) is False
        assert IgdDevice.is_profile_device(empty_descriptor) is False
        assert IgdDevice.is_profile_device(igd_device) is True

    @pytest.mark.asyncio
    async def test_subscribe_manual_resubscribe(self) -> None:
        """Test subscribing, resub, unsub, without auto_resubscribe."""
        now = time.monotonic()
        requester = UpnpTestRequester(RESPONSE_MAP)
        factory = UpnpFactory(requester)
        device = await factory.async_create_device("http://dlna_dmr:1234/device.xml")
        notify_server = UpnpTestNotifyServer(
            requester=requester,
            source=("192.168.1.2", 8090),
        )
        event_handler = notify_server.event_handler
        profile = DmrDevice(device, event_handler=event_handler)

        # Test subscription
        timeout = await profile.async_subscribe_services(auto_resubscribe=False)
        assert timeout is not None
        # Timeout incorporates time tolerance, and is minimal renewal time
        assert timedelta(seconds=(149 - 60)) <= timeout <= timedelta(seconds=(151 - 60))

        assert set(profile._subscriptions.keys()) == {
            "uuid:dummy-avt1",
            "uuid:dummy-cm1",
            "uuid:dummy",
        }

        # 3 timeouts, ~ 150, ~ 175, and ~ 300 seconds
        timeouts = sorted(profile._subscriptions.values())
        assert timeouts[0] == pytest.approx(now + 150, abs=1)
        assert timeouts[1] == pytest.approx(now + 175, abs=1)
        assert timeouts[2] == pytest.approx(now + 300, abs=1)

        # Tweak timeouts to check resubscription did something
        requester.response_map[
            ("SUBSCRIBE", "http://dlna_dmr:1234/upnp/event/RenderingControl1")
        ][1]["timeout"] = "Second-90"

        # Check subscriptions again, now timeouts should have changed
        timeout = await profile.async_subscribe_services(auto_resubscribe=False)
        assert timeout is not None
        assert timedelta(seconds=(89 - 60)) <= timeout <= timedelta(seconds=(91 - 60))
        assert set(profile._subscriptions.keys()) == {
            "uuid:dummy-avt1",
            "uuid:dummy-cm1",
            "uuid:dummy",
        }
        timeouts = sorted(profile._subscriptions.values())
        assert timeouts[0] == pytest.approx(now + 90, abs=1)
        assert timeouts[1] == pytest.approx(now + 150, abs=1)

        # Test unsubscription
        await profile.async_unsubscribe_services()
        assert not profile._subscriptions

    @pytest.mark.asyncio
    async def test_subscribe_auto_resubscribe(self) -> None:
        """Test subscribing, resub, unsub, with auto_resubscribe."""
        now = time.monotonic()
        requester = UpnpTestRequester(RESPONSE_MAP)
        factory = UpnpFactory(requester)
        device = await factory.async_create_device("http://dlna_dmr:1234/device.xml")
        notify_server = UpnpTestNotifyServer(
            requester=requester,
            source=("192.168.1.2", 8090),
        )
        event_handler = notify_server.event_handler
        profile = DmrDevice(device, event_handler=event_handler)

        # Tweak timeouts to get a resubscription in a time suitable for testing.
        # Resubscription tolerance (60 seconds) + 1 second to get set up
        requester.response_map[
            ("SUBSCRIBE", "http://dlna_dmr:1234/upnp/event/RenderingControl1")
        ][1]["timeout"] = "Second-61"

        # Test subscription
        timeout = await profile.async_subscribe_services(auto_resubscribe=True)
        assert timeout is None
        assert profile.is_subscribed is True

        # Check subscriptions are correct
        assert set(profile._subscriptions.keys()) == {
            "uuid:dummy-avt1",
            "uuid:dummy-cm1",
            "uuid:dummy",
        }
        timeouts = sorted(profile._subscriptions.values())
        assert timeouts[0] == pytest.approx(now + 61, abs=1)
        assert timeouts[1] == pytest.approx(now + 150, abs=1)

        # Check task is running
        assert isinstance(profile._resubscriber_task, asyncio.Task)
        assert not profile._resubscriber_task.cancelled()
        assert not profile._resubscriber_task.done()

        # Re-tweak timeouts to check resubscription did something
        requester.response_map[
            ("SUBSCRIBE", "http://dlna_dmr:1234/upnp/event/AVTransport1")
        ][1]["timeout"] = "Second-90"

        # Wait for an auto-resubscribe
        await asyncio.sleep(1.5)
        now = time.monotonic()

        # Check subscriptions and task again
        assert set(profile._subscriptions.keys()) == {
            "uuid:dummy-avt1",
            "uuid:dummy-cm1",
            "uuid:dummy",
        }
        timeouts = sorted(profile._subscriptions.values())
        assert timeouts[0] == pytest.approx(now + 61, abs=1)
        assert timeouts[1] == pytest.approx(now + 90, abs=1)
        assert isinstance(profile._resubscriber_task, asyncio.Task)
        assert not profile._resubscriber_task.cancelled()
        assert not profile._resubscriber_task.done()
        assert profile.is_subscribed is True

        # Unsubscribe
        await profile.async_unsubscribe_services()

        # Task and subscriptions should be gone
        assert profile._resubscriber_task is None
        assert not profile._subscriptions
        assert profile.is_subscribed is False

    @pytest.mark.asyncio
    async def test_subscribe_fail(self) -> None:
        """Test subscribing fails with UpnpError if device is offline."""
        requester = UpnpTestRequester(RESPONSE_MAP)
        factory = UpnpFactory(requester)
        device = await factory.async_create_device("http://dlna_dmr:1234/device.xml")
        notify_server = UpnpTestNotifyServer(
            requester=requester,
            source=("192.168.1.2", 8090),
        )
        event_handler = notify_server.event_handler
        profile = DmrDevice(device, event_handler=event_handler)

        # First request is fine, 2nd raises an exception, when trying to subscribe
        requester.exceptions.append(None)
        requester.exceptions.append(UpnpCommunicationError())

        with pytest.raises(UpnpCommunicationError):
            await profile.async_subscribe_services(True)

        # Subscriptions and resubscribe task should not exist
        assert not profile._subscriptions
        assert profile._resubscriber_task is None
        assert profile.is_subscribed is False

    @pytest.mark.asyncio
    async def test_subscribe_rejected(self) -> None:
        """Test subscribing rejected by device."""
        requester = UpnpTestRequester(RESPONSE_MAP)
        factory = UpnpFactory(requester)
        device = await factory.async_create_device("http://dlna_dmr:1234/device.xml")
        notify_server = UpnpTestNotifyServer(
            requester=requester,
            source=("192.168.1.2", 8090),
        )
        event_handler = notify_server.event_handler
        profile = DmrDevice(device, event_handler=event_handler)

        # All requests give a response error
        requester.exceptions.append(UpnpResponseError(status=501))
        requester.exceptions.append(UpnpResponseError(status=501))

        with pytest.raises(UpnpResponseError):
            await profile.async_subscribe_services(True)

        # Subscriptions and resubscribe task should not exist
        assert not profile._subscriptions
        assert profile._resubscriber_task is None
        assert profile.is_subscribed is False

    @pytest.mark.asyncio
    async def test_auto_resubscribe_fail(self) -> None:
        """Test auto-resubscription when the device goes offline."""
        requester = UpnpTestRequester(RESPONSE_MAP)
        factory = UpnpFactory(requester)
        device = await factory.async_create_device("http://dlna_dmr:1234/device.xml")
        notify_server = UpnpTestNotifyServer(
            requester=requester,
            source=("192.168.1.2", 8090),
        )
        event_handler = notify_server.event_handler
        profile = DmrDevice(device, event_handler=event_handler)
        assert device.available is True

        # Register an event handler
        on_event_mock = Mock(return_value=None)
        profile.on_event = on_event_mock

        # Setup for auto-resubscription
        requester.response_map[
            ("SUBSCRIBE", "http://dlna_dmr:1234/upnp/event/RenderingControl1")
        ][1]["timeout"] = "Second-61"
        await profile.async_subscribe_services(auto_resubscribe=True)

        # Exception raised when trying to resubscribe and subsequent retry subscribe
        requester.exceptions.append(UpnpCommunicationError("resubscribe"))
        requester.exceptions.append(UpnpConnectionError("subscribe"))

        # Wait for an auto-resubscribe
        await asyncio.sleep(1.5)

        # Device should now be offline, and an event notification sent
        assert device.available is False
        on_event_mock.assert_called_once_with(
            device.services["urn:schemas-upnp-org:service:RenderingControl:1"], []
        )
        # Device will still be subscribed because a notification was sent via
        # on_event instead of raising an exception.
        assert profile.is_subscribed is True

        # Unsubscribe should still work
        await profile.async_unsubscribe_services()
        assert profile.is_subscribed is False

        # Task and subscriptions should be gone
        assert profile._resubscriber_task is None
        assert not profile._subscriptions
        assert profile.is_subscribed is False

    @pytest.mark.asyncio
    async def test_subscribe_no_event_handler(self) -> None:
        """Test no event handler."""
        requester = UpnpTestRequester(RESPONSE_MAP)
        factory = UpnpFactory(requester)
        device = await factory.async_create_device("http://dlna_dmr:1234/device.xml")
        profile = DmrDevice(device, event_handler=None)

        # Doesn't error, but also doesn't do anything.
        await profile.async_subscribe_services()

    @pytest.mark.asyncio
    async def test_poll_state_variables(self) -> None:
        """Test polling state variables by calling a Get* action."""
        requester = UpnpTestRequester(RESPONSE_MAP)
        requester.response_map[
            ("POST", "http://dlna_dmr:1234/upnp/control/AVTransport1")
        ] = (200, {}, read_file("dlna/dmr/action_GetPositionInfo.xml"))

        factory = UpnpFactory(requester)
        device = await factory.async_create_device("http://dlna_dmr:1234/device.xml")
        notify_server = UpnpTestNotifyServer(
            requester=requester,
            source=("192.168.1.2", 8090),
        )
        event_handler = notify_server.event_handler
        profile = DmrDevice(device, event_handler=event_handler)
        assert device.available is True

        # Register an event handler, it should be called when variable is updated
        on_event_mock = Mock(return_value=None)
        profile.on_event = on_event_mock
        assert profile.is_subscribed is False

        # Check state variables are currently empty
        assert profile.media_track_number is None
        assert profile.media_duration is None
        assert profile.current_track_uri is None
        assert profile._current_track_meta_data is None
        assert profile.media_title is None
        assert profile.media_artist is None

        # Call the Get action
        await profile._async_poll_state_variables(
            "AVT", ["GetPositionInfo"], InstanceID=0
        )

        # on_event should be called with all changed variables
        expected_service = device.services["urn:schemas-upnp-org:service:AVTransport:1"]
        expected_changes = [
            expected_service.state_variables[name]
            for name in (
                "CurrentTrack",
                "CurrentTrackDuration",
                "CurrentTrackMetaData",
                "CurrentTrackURI",
                "RelativeTimePosition",
                "AbsoluteTimePosition",
                "RelativeCounterPosition",
                "AbsoluteCounterPosition",
            )
        ]
        on_event_mock.assert_called_once_with(expected_service, expected_changes)

        # Corresponding state variables should be updated
        assert profile.media_track_number == 1
        assert profile.media_duration == 194
        assert profile.current_track_uri == "uri://1.mp3"
        assert profile._current_track_meta_data is not None
        assert profile.media_title == "Test track"
        assert profile.media_artist == "A & B > C"
