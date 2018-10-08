# -*- coding: utf-8 -*-
"""UPnP base-profile module."""

from typing import Optional

from async_upnp_client import UpnpAction
from async_upnp_client import UpnpDevice
from async_upnp_client import UpnpEventHandler
from async_upnp_client import UpnpService
from async_upnp_client import UpnpStateVariable


class UpnpProfileDevice:
    """
    Base class for UpnpProfileDevices.

    Override _SERVICE_TYPES for aliases.
    """

    _SERVICE_TYPES = {}

    def __init__(self,
                 device: UpnpDevice,
                 event_handler: UpnpEventHandler) -> None:
        """Initializer."""
        self._device = device
        self._event_handler = event_handler
        self.on_event = None

    @property
    def name(self) -> str:
        """Get the name of the device."""
        return self._device.name

    @property
    def udn(self) -> str:
        """Get the UDN of the device."""
        return self._device.udn

    def _service(self, service_type_abbreviation: str) -> Optional[UpnpService]:
        """Get UpnpService by service_type or alias."""
        if not self._device:
            return None

        if service_type_abbreviation not in self._SERVICE_TYPES:
            return None

        for service_type in self._SERVICE_TYPES[service_type_abbreviation]:
            service = self._device.service(service_type)
            if service:
                return service

        return None

    def _state_variable(self, service_name: str,
                        state_variable_name: str) -> Optional[UpnpStateVariable]:
        """Get state_variable from service."""
        service = self._service(service_name)
        if not service:
            return None

        return service.state_variable(state_variable_name)

    def _action(self, service_name: str, action_name: str) -> Optional[UpnpAction]:
        """Check if service has action."""
        service = self._service(service_name)
        if not service:
            return None

        return service.action(action_name)
