"""Unit tests for profile."""
# pylint: disable=protected-access

import asyncio
import time
from datetime import timedelta
from unittest.mock import Mock

import pytest

from async_upnp_client import UpnpEventHandler, UpnpFactory
from async_upnp_client.exceptions import UpnpCommunicationError, UpnpConnectionError
from async_upnp_client.profiles.dlna import DmrDevice

from ..upnp_test_requester import RESPONSE_MAP, UpnpTestRequester


class TestUpnpProfileDevice:
    """Test UPnpProfileDevice."""

    # pylint: disable=no-self-use

    @pytest.mark.asyncio
    async def test_action_exists(self) -> None:
        """Test getting existing action."""
        requester = UpnpTestRequester(RESPONSE_MAP)
        factory = UpnpFactory(requester)
        device = await factory.async_create_device("http://dlna_dmr:1234/dmr")
        event_handler = UpnpEventHandler("http://localhost:11302", requester)
        profile = DmrDevice(device, event_handler=event_handler)

        # doesn't error
        assert profile._action("RC", "GetMute") is not None

    @pytest.mark.asyncio
    async def test_action_not_exists(self) -> None:
        """Test getting non-existing action."""
        requester = UpnpTestRequester(RESPONSE_MAP)
        factory = UpnpFactory(requester)
        device = await factory.async_create_device("http://dlna_dmr:1234/dmr")
        event_handler = UpnpEventHandler("http://localhost:11302", requester)
        profile = DmrDevice(device, event_handler=event_handler)

        # doesn't error
        assert profile._action("RC", "NonExisting") is None

    @pytest.mark.asyncio
    async def test_icon(self) -> None:
        """Test getting an icon returns the best available."""
        requester = UpnpTestRequester(RESPONSE_MAP)
        factory = UpnpFactory(requester)
        device = await factory.async_create_device("http://dlna_dmr:1234/dmr")
        event_handler = UpnpEventHandler("http://localhost:11302", requester)
        profile = DmrDevice(device, event_handler=event_handler)

        assert profile.icon == "http://dlna_dmr:1234/device_icon_120.png"

    @pytest.mark.asyncio
    async def test_subscribe_manual_resubscribe(self) -> None:
        """Test subscribing, resub, unsub, without auto_resubscribe."""
        now = time.monotonic()
        requester = UpnpTestRequester(RESPONSE_MAP)
        factory = UpnpFactory(requester)
        device = await factory.async_create_device("http://dlna_dmr:1234/dmr")
        event_handler = UpnpEventHandler("http://localhost:11302", requester)
        profile = DmrDevice(device, event_handler=event_handler)

        # Test subscription
        timeout = await profile.async_subscribe_services(auto_resubscribe=False)
        assert timeout is not None
        # Timeout incorporates time tolerance, and is minimal renewal time
        assert timedelta(seconds=(149 - 60)) <= timeout <= timedelta(seconds=(151 - 60))

        assert set(profile._subscriptions.keys()) == {
            "uuid:dummy-avt1",
            "uuid:dummy",
        }

        # 2 timeouts, ~ 150 and ~ 300 seconds
        timeouts = sorted(profile._subscriptions.values())
        assert timeouts[0] == pytest.approx(now + 150, abs=1)
        assert timeouts[1] == pytest.approx(now + 300, abs=1)

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
            "uuid:dummy",
        }
        timeouts = sorted(profile._subscriptions.values())
        assert timeouts[0] == pytest.approx(now + 90, abs=1)
        assert timeouts[1] == pytest.approx(now + 150, abs=1)

        # Test unsubscription
        await profile.async_unsubscribe_services()
        assert profile._subscriptions == {}

    @pytest.mark.asyncio
    async def test_subscribe_auto_resubscribe(self) -> None:
        """Test subscribing, resub, unsub, with auto_resubscribe."""
        now = time.monotonic()
        requester = UpnpTestRequester(RESPONSE_MAP)
        factory = UpnpFactory(requester)
        device = await factory.async_create_device("http://dlna_dmr:1234/dmr")
        event_handler = UpnpEventHandler("http://localhost:11302", requester)
        profile = DmrDevice(device, event_handler=event_handler)

        # Tweak timeouts to get a resubscription in a time suitable for testing.
        # Resubscription tolerance (60 seconds) + 1 second to get set up
        requester.response_map[
            ("SUBSCRIBE", "http://dlna_dmr:1234/upnp/event/RenderingControl1")
        ][1]["timeout"] = "Second-61"

        # Test subscription
        timeout = await profile.async_subscribe_services(auto_resubscribe=True)
        assert timeout is None

        # Check subscriptions are correct
        assert set(profile._subscriptions.keys()) == {
            "uuid:dummy-avt1",
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
            "uuid:dummy",
        }
        timeouts = sorted(profile._subscriptions.values())
        assert timeouts[0] == pytest.approx(now + 61, abs=1)
        assert timeouts[1] == pytest.approx(now + 90, abs=1)
        assert isinstance(profile._resubscriber_task, asyncio.Task)
        assert not profile._resubscriber_task.cancelled()
        assert not profile._resubscriber_task.done()

        # Unsubscribe
        await profile.async_unsubscribe_services()

        # Task and subscriptions should be gone
        assert profile._resubscriber_task is None
        assert profile._subscriptions == {}

    @pytest.mark.asyncio
    async def test_subscribe_fail(self) -> None:
        """Test subscribing fails with UpnpError if device is offline."""
        requester = UpnpTestRequester(RESPONSE_MAP)
        factory = UpnpFactory(requester)
        device = await factory.async_create_device("http://dlna_dmr:1234/dmr")
        event_handler = UpnpEventHandler("http://localhost:11302", requester)
        profile = DmrDevice(device, event_handler=event_handler)

        # First request is fine, 2nd raises an exception, when trying to subscribe
        requester.exceptions.append(None)
        requester.exceptions.append(UpnpCommunicationError())

        with pytest.raises(UpnpCommunicationError):
            await profile.async_subscribe_services(True)

        # Subscriptions and resubscribe task should not exist
        assert profile._subscriptions == {}
        assert profile._resubscriber_task is None

    @pytest.mark.asyncio
    async def test_auto_resubscribe_fail(self) -> None:
        """Test auto-resubscription when the device goes offline."""
        requester = UpnpTestRequester(RESPONSE_MAP)
        factory = UpnpFactory(requester)
        device = await factory.async_create_device("http://dlna_dmr:1234/dmr")
        event_handler = UpnpEventHandler("http://localhost:11302", requester)
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

        # Unsubscribe should still work
        await profile.async_unsubscribe_services()

        # Task and subscriptions should be gone
        assert profile._resubscriber_task is None
        assert profile._subscriptions == {}
