"""Unit tests for profile."""

import pytest  # type: ignore

from async_upnp_client import UpnpEventHandler, UpnpFactory
from async_upnp_client.profiles.dlna import DmrDevice

from ..upnp_test_requester import RESPONSE_MAP, UpnpTestRequester


class TestUpnpProfileDevice:
    """Test UPnpProfileDevice."""

    @pytest.mark.asyncio
    async def test_action_exists(self):
        """Test getting existing action."""
        r = UpnpTestRequester(RESPONSE_MAP)
        factory = UpnpFactory(r)
        device = await factory.async_create_device("http://localhost:1234/dmr")
        event_handler = UpnpEventHandler("http://localhost:11302", r)
        profile = DmrDevice(device, event_handler=event_handler)

        # doesn't error
        assert profile._action("RC", "GetMute") is not None

    @pytest.mark.asyncio
    async def test_action_not_exists(self):
        """Test getting non-existing action."""
        r = UpnpTestRequester(RESPONSE_MAP)
        factory = UpnpFactory(r)
        device = await factory.async_create_device("http://localhost:1234/dmr")
        event_handler = UpnpEventHandler("http://localhost:11302", r)
        profile = DmrDevice(device, event_handler=event_handler)

        # doesn't error
        assert profile._action("RC", "NonExisting") is None

    @pytest.mark.asyncio
    async def test_icon(self):
        """Test getting an icon returns the best available."""
        r = UpnpTestRequester(RESPONSE_MAP)
        factory = UpnpFactory(r)
        device = await factory.async_create_device("http://localhost:1234/dmr")
        event_handler = UpnpEventHandler("http://localhost:11302", r)
        profile = DmrDevice(device, event_handler=event_handler)

        assert profile.icon == "http://localhost:1234/device_icon_120.png"


# TODO: Test resubscribe
