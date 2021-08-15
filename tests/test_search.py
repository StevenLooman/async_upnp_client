"""Unit tests for search."""

from async_upnp_client.search import SSDPListener


def test_create_ssdp_listener_with_alternate_target():
    """Create a SSDPListener on an alternate target."""

    async def _dummy_callback(*args):
        pass

    yeelight_target = ("239.255.255.250", 1982)
    yeelight_service_type = "wifi_bulb"
    listener = SSDPListener(
        async_callback=_dummy_callback,
        async_connect_callback=_dummy_callback,
        service_type=yeelight_service_type,
        target=yeelight_target,
    )

    assert listener.target == yeelight_target
    assert listener.service_type == yeelight_service_type
    assert listener.async_callback == _dummy_callback
    assert listener.async_connect_callback == _dummy_callback
