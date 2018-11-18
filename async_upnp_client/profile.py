# -*- coding: utf-8 -*-
"""UPnP base-profile module."""

import logging

from datetime import timedelta
from typing import Dict
from typing import List
from typing import Optional

from async_upnp_client import UpnpAction
from async_upnp_client import UpnpDevice
from async_upnp_client import UpnpEventHandler
from async_upnp_client import UpnpService
from async_upnp_client import UpnpStateVariable
from async_upnp_client.discovery import async_discover


_LOGGER = logging.getLogger(__name__)


SUBSCRIBE_TIMEOUT = timedelta(minutes=30)


class UpnpProfileDevice:
    """
    Base class for UpnpProfileDevices.

    Override _SERVICE_TYPES for aliases.
    """

    DEVICE_TYPES = []

    _SERVICE_TYPES = {}

    @classmethod
    async def async_discover(cls) -> Dict:
        """
        Discovery this device type.

        This only return discovery info, not a profile itself.

        :return:
        """
        return [
            device
            for device in await async_discover()
            if device['st'] in cls.DEVICE_TYPES
        ]

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

    def _interesting_service(self, service: UpnpService) -> bool:
        """Check if service is a service we're interested in."""
        service_type = service.service_type
        for service_types in self._SERVICE_TYPES.values():
            if service_type in service_types:
                return True

        return False

    async def async_subscribe_services(self) -> timedelta:
        """(Re-)Subscribe to services."""
        for service in self._device.services.values():
            # ensure we are interested in this service_type
            if not self._interesting_service(service):
                continue

            service.on_event = self._on_event
            if self._event_handler.sid_for_service(service) is None:
                _LOGGER.debug('Subscribing to service: %s', service)
                success, _ = \
                    await self._event_handler.async_subscribe(service, timeout=SUBSCRIBE_TIMEOUT)
                if not success:
                    _LOGGER.debug('Failed subscribing to: %s', service)
            else:
                _LOGGER.debug('Resubscribing to service: %s', service)
                success, _ = \
                    await self._event_handler.async_resubscribe(service, timeout=SUBSCRIBE_TIMEOUT)

                # could not renew subscription, try subscribing again
                if not success:
                    _LOGGER.debug('Failed resubscribing to: %s', service)

                    success, _ = \
                        await self._event_handler.async_subscribe(service,
                                                                  timeout=SUBSCRIBE_TIMEOUT)
                    if not success:
                        _LOGGER.debug('Failed subscribing to: %s', service)

        return SUBSCRIBE_TIMEOUT

    async def async_unsubscribe_services(self):
        """Unsubscribe from all subscribed services."""
        await self._event_handler.async_unsubscribe_all()

    def _on_event(self, service: UpnpService, state_variables: List[UpnpStateVariable]):
        """
        State variable(s) changed. Override to handle events.

        :param service Service which sent the event.
        :param state_variables State variables which have been changed.
        """
        pass
