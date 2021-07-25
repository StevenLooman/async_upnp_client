# -*- coding: utf-8 -*-
"""UPnP base-profile module."""

import asyncio
import logging
import time
from datetime import timedelta
from ipaddress import IPv4Address
from typing import Dict, List, Mapping, Optional, Sequence, Set

from async_upnp_client.client import (
    EventCallbackType,
    UpnpAction,
    UpnpDevice,
    UpnpService,
    UpnpStateVariable,
)
from async_upnp_client.event_handler import UpnpEventHandler
from async_upnp_client.exceptions import UpnpConnectionError, UpnpError
from async_upnp_client.search import async_search
from async_upnp_client.ssdp import SSDP_MX

_LOGGER = logging.getLogger(__name__)


SUBSCRIBE_TIMEOUT = timedelta(minutes=9)
RESUBSCRIBE_TOLERANCE = timedelta(minutes=1)
RESUBSCRIBE_TOLERANCE_SECS = RESUBSCRIBE_TOLERANCE.total_seconds()


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
        self.on_event: Optional[EventCallbackType] = None
        self._icon: Optional[str] = None
        # Map of SID to renewal timestamp (monotonic clock seconds)
        self._subscriptions: Dict[str, float] = {}
        self._resubscriber_task: Optional[asyncio.Task] = None

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

    @property
    def icon(self) -> Optional[str]:
        """Get a URL for the biggest icon for this device."""
        if not self.device.icons:
            return None
        if not self._icon:
            icon_mime_preference = {"image/png": 3, "image/jpeg": 2, "image/gif": 1}
            icons = [icon for icon in self.device.icons if icon.url]
            icons = sorted(
                icons,
                # Sort by area, then colour depth, then preferred mimetype
                key=lambda icon: (
                    icon.width * icon.height,
                    icon.depth,
                    icon_mime_preference.get(icon.mimetype, 0),
                ),
                reverse=True,
            )
            self._icon = icons[0].url
        return self._icon

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

    async def _async_resubscribe_services(
        self, now: Optional[float] = None, notify_errors: bool = False
    ) -> None:
        """Renew existing subscriptions.

        :param now: time.monotonic reference for current time
        :param notify_errors: Call on_event in case of error instead of raising
        """
        if now is None:
            now = time.monotonic()
        renewal_threshold = now - RESUBSCRIBE_TOLERANCE_SECS

        _LOGGER.debug("Resubscribing to services with threshold %f", renewal_threshold)

        for sid, renewal_time in list(self._subscriptions.items()):
            if renewal_time < renewal_threshold:
                _LOGGER.debug("Skipping %s with renewal_time %f", sid, renewal_time)
                continue
            _LOGGER.debug("Resubscribing to %s with renewal_time %f", sid, renewal_time)
            # Subscription is going to be changed, no matter what
            del self._subscriptions[sid]
            # Determine service for on_event call in case of failure
            service = self._event_handler.service_for_sid(sid)
            if not service:
                _LOGGER.error("Subscription for %s was lost", sid)
                continue

            try:
                new_sid, timeout = await self._event_handler.async_resubscribe(
                    sid, timeout=SUBSCRIBE_TIMEOUT
                )
            except UpnpError as err:
                if isinstance(err, UpnpConnectionError):
                    # Device has gone offline
                    self.device.available = False
                _LOGGER.error("Failed (re-)subscribing to: %s, reason: %s", sid, err)
                if notify_errors:
                    # Notify event listeners that something has changed
                    self._on_event(service, [])
                else:
                    raise
            else:
                self._subscriptions[new_sid] = now + timeout.total_seconds()

    async def _resubscribe_loop(self) -> None:
        """Periodically resubscribes to current subscriptions."""
        _LOGGER.debug("_resubscribe_loop started")
        while self._subscriptions:
            next_renewal = min(self._subscriptions.values())
            wait_time = next_renewal - time.monotonic() - RESUBSCRIBE_TOLERANCE_SECS
            _LOGGER.debug("Resubscribing in %f seconds", wait_time)
            if wait_time > 0:
                await asyncio.sleep(wait_time)

            await self._async_resubscribe_services(notify_errors=True)

        _LOGGER.debug("_resubscribe_loop ended because of no subscriptions")

    async def _update_resubscriber_task(self) -> None:
        """Start or stop the resubscriber task, depending on having subscriptions."""
        # Clear out done task to make later logic easier
        if self._resubscriber_task and self._resubscriber_task.cancelled():
            self._resubscriber_task = None

        if self._subscriptions and not self._resubscriber_task:
            _LOGGER.debug("Creating resubscribe_task")
            # pylint: disable=fixme
            # TODO: Use create_task instead of ensure_future with Python 3.8+
            # self._resubscriber_task = asyncio.create_task(
            # self._resubscribe_loop(),
            # name=f"UpnpProfileDevice({self.name})._resubscriber_task",
            # )
            self._resubscriber_task = asyncio.ensure_future(self._resubscribe_loop())

        if not self._subscriptions and self._resubscriber_task:
            _LOGGER.debug("Cancelling resubscribe_task")
            self._resubscriber_task.cancel()
            try:
                await self._resubscriber_task
            except asyncio.CancelledError:
                pass
            self._resubscriber_task = None

    async def async_subscribe_services(
        self, auto_resubscribe: bool = False
    ) -> Optional[timedelta]:
        """(Re-)Subscribe to services.

        :param auto_resubscribe: Automatically resubscribe to subscriptions
            before they expire. If this is enabled, failure to resubscribe will
            be indicated by on_event being called with the failed service and an
            empty state_variables list.
        :return: time until this next needs to be called, or None if manual
            resubscription is not needed.
        :raise UpnpError or subclass: Failed to subscribe to all interesting
            services.
        """
        # Using time.monotonic to avoid problems with system clock changes
        now = time.monotonic()

        try:
            if self._subscriptions:
                # Resubscribe existing subscriptions
                await self._async_resubscribe_services(now)
            else:
                # Subscribe to services we are interested in
                for service in self.device.services.values():
                    if not self._interesting_service(service):
                        continue
                    _LOGGER.debug("Subscribing to service: %s", service)
                    service.on_event = self._on_event
                    new_sid, timeout = await self._event_handler.async_subscribe(
                        service, timeout=SUBSCRIBE_TIMEOUT
                    )
                    self._subscriptions[new_sid] = now + timeout.total_seconds()
        except UpnpError as err:
            _LOGGER.error("Failed subscribing to service: %s", err)
            # Unsubscribe anything that was subscribed, no half-done subscriptions
            try:
                await self.async_unsubscribe_services()
            except UpnpError:
                pass
            raise

        if not self._subscriptions:
            return None

        if auto_resubscribe:
            await self._update_resubscriber_task()
            return None

        lowest_timeout_delta = min(self._subscriptions.values()) - now
        resubcription_timeout = (
            timedelta(seconds=lowest_timeout_delta) - RESUBSCRIBE_TOLERANCE
        )
        return max(resubcription_timeout, timedelta(seconds=0))

    async def async_unsubscribe_services(self) -> None:
        """Unsubscribe from all of our subscribed services."""
        # Delete list of subscriptions and cancel renewal before unsubcribing
        # to avoid unsub-resub race.
        subscriptions = self._subscriptions
        self._subscriptions = {}
        await self._update_resubscriber_task()

        for sid in subscriptions:
            try:
                await self._event_handler.async_unsubscribe(sid)
            except UpnpError as err:
                _LOGGER.debug("Failed unsubscribing to: %s, reason: %s", sid, err)
            except KeyError:
                _LOGGER.warning(
                    "%s was already unsubscribed. AiohttpNotifyServer was "
                    "probably stopped before we could unsubscribe.",
                    sid,
                )

    @property
    def is_subscribed(self) -> bool:
        """Get current service subscription state."""
        return bool(self._subscriptions)

    def _on_event(
        self, service: UpnpService, state_variables: Sequence[UpnpStateVariable]
    ) -> None:
        """
        State variable(s) changed. Override to handle events.

        :param service Service which sent the event.
        :param state_variables State variables which have been changed.
        """
        if self.on_event:
            self.on_event(service, state_variables)  # pylint: disable=not-callable
