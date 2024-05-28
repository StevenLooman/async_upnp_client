Subscribe to IGD to reduce number of polls.

This also simplifies the returned IgdState from IgdDevice.async_get_traffic_and_status_data(), as the items from StatusInfo are now diectly added to IgdState.

As a bonus, extend the dummy_router to support subscribing and use evented state variables ExternalIPAddress and ConnectionStatus.
