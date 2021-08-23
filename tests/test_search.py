"""Unit tests for search."""
# pylint: disable=protected-access

from typing import Any

from async_upnp_client.search import SSDPListener
from async_upnp_client.ssdp import SSDP_IP_V4


def test_create_ssdp_listener_with_alternate_target() -> None:
    """Create a SSDPListener on an alternate target."""

    async def _dummy_callback(*_: Any) -> None:
        # Nop.
        pass

    yeelight_target = (SSDP_IP_V4, 1982)
    yeelight_service_type = "wifi_bulb"
    listener = SSDPListener(
        async_callback=_dummy_callback,
        async_connect_callback=_dummy_callback,
        service_type=yeelight_service_type,
        target=yeelight_target,
    )

    assert listener._target == yeelight_target
    assert listener.service_type == yeelight_service_type
    # pylint: disable=comparison-with-callable
    assert listener.async_callback == _dummy_callback
    assert listener.async_connect_callback == _dummy_callback
