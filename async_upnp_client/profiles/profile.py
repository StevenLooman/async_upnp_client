# -*- coding: utf-8 -*-
"""UPnP base-profile module."""

import logging
from datetime import timedelta
from ipaddress import IPv4Address
from typing import Dict, List, Mapping, Optional, Sequence, Set

from async_upnp_client.client import EventCallbackType  # pylint: disable=unused-import
from async_upnp_client.client import (
    UpnpAction,
    UpnpDevice,
    UpnpService,
    UpnpStateVariable,
)
from async_upnp_client.event_handler import UpnpEventHandler
from async_upnp_client.search import async_search
from async_upnp_client.ssdp import SSDP_MX

_LOGGER = logging.getLogger(__name__)


SUBSCRIBE_TIMEOUT = timedelta(minutes=9)


class UpnpProfileDevice:
    """
    Base class for UpnpProfileDevices.

    Override _SERVICE_TYPES for aliases.
    """

    DEVICE_TYPES: List[str] = []

    _SERVICE_TYPES: Dict[str, Set[str]] = {}

    @classmethod
    async def async_search(
        cls, source_ip: Optional[IPv4Address] = None, timeout: int = SSDP_MX
    ) -> Set[Mapping[str, str]]:
        """
        Search for this device type.

        This only returns search info, not a profile itself.

        :param source_ip Source IP to scan from
        :param timeout Timeout to use
        :return: Set of devices (dicts) found
        """
        responses = set()

        async def on_response(data: Mapping[str, str]) -> None:
            if "st" in data and data["st"] in cls.DEVICE_TYPES:
                responses.add(data)

        await async_search(
            async_callback=on_response, source_ip=source_ip, timeout=timeout
        )

        return responses

    @classmethod
    async def async_discover(cls) -> Set[Mapping[str, str]]:
        """Alias for async_search."""
        return await cls.async_search()

    def __init__(self, device: UpnpDevice, event_handler: UpnpEventHandler) -> None:
        """Initialize."""
        self.device = device
        self._event_handler = event_handler
        self.on_event = None

    @property
    def name(self) -> str:
        """Get the name of the device."""
        return self.device.name

    @property
    def manufacturer(self) -> str:
        """Get the manufacturer of this device."""
        return self.device.manufacturer

    @property
    def model_description(self) -> Optional[str]:
        """Get the model description of this device."""
        return self.device.model_description

    @property
    def model_name(self) -> str:
        """Get the model name of this device."""
        return self.device.model_name

    @property
    def model_number(self) -> Optional[str]:
        """Get the model number of this device."""
        return self.device.model_number

    @property
    def serial_number(self) -> Optional[str]:
        """Get the serial number of this device."""
        return self.device.serial_number

    @property
    def udn(self) -> str:
        """Get the UDN of the device."""
        return self.device.udn

    @property
    def device_type(self) -> str:
        """Get the device type of this device."""
        return self.device.device_type

    def _service(self, service_type_abbreviation: str) -> Optional[UpnpService]:
        """Get UpnpService by service_type or alias."""
        if not self.device:
            return None

        if service_type_abbreviation not in self._SERVICE_TYPES:
            return None

        for service_type in self._SERVICE_TYPES[service_type_abbreviation]:
            if self.device.has_service(service_type):
                return self.device.service(service_type)

        return None

    def _state_variable(
        self, service_name: str, state_variable_name: str
    ) -> Optional[UpnpStateVariable]:
        """Get state_variable from service."""
        service = self._service(service_name)
        if not service:
            return None

        if not service.has_state_variable(state_variable_name):
            return None

        return service.state_variable(state_variable_name)

    def _action(self, service_name: str, action_name: str) -> Optional[UpnpAction]:
        """Check if service has action."""
        service = self._service(service_name)
        if not service:
            return None

        if not service.has_action(action_name):
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
        for service in self.device.services.values():
            # ensure we are interested in this service_type
            if not self._interesting_service(service):
                continue

            on_event: EventCallbackType = self._on_event
            service.on_event = on_event
            if self._event_handler.sid_for_service(service) is None:
                _LOGGER.debug("Subscribing to service: %s", service)
                success, _ = await self._event_handler.async_subscribe(
                    service, timeout=SUBSCRIBE_TIMEOUT
                )
                if not success:
                    _LOGGER.debug("Failed subscribing to: %s", service)
            else:
                _LOGGER.debug("Resubscribing to service: %s", service)
                success, _ = await self._event_handler.async_resubscribe(
                    service, timeout=SUBSCRIBE_TIMEOUT
                )

                # could not renew subscription, try subscribing again
                if not success:
                    _LOGGER.debug("Failed resubscribing to: %s", service)

                    success, _ = await self._event_handler.async_subscribe(
                        service, timeout=SUBSCRIBE_TIMEOUT
                    )
                    if not success:
                        _LOGGER.debug("Failed subscribing to: %s", service)

        return SUBSCRIBE_TIMEOUT

    async def async_unsubscribe_services(self) -> None:
        """Unsubscribe from all subscribed services."""
        await self._event_handler.async_unsubscribe_all()

    def _on_event(
        self, service: UpnpService, state_variables: Sequence[UpnpStateVariable]
    ) -> None:
        """
        State variable(s) changed. Override to handle events.

        :param service Service which sent the event.
        :param state_variables State variables which have been changed.
        """
        if self.on_event:
            # pylint: disable=not-callable
            self.on_event(service, state_variables)
