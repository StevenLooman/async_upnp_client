# -*- coding: utf-8 -*-
"""async_upnp_client.ssdp_listener module."""

import logging
import re
from asyncio import Lock
from asyncio.events import AbstractEventLoop
from contextlib import AbstractAsyncContextManager
from datetime import datetime, timedelta
from ipaddress import ip_address
from types import TracebackType
from typing import Any, Awaitable, Callable, Dict, Mapping, Optional, Set, Tuple, Type
from urllib.parse import urlparse

from async_upnp_client.advertisement import SsdpAdvertisementListener
from async_upnp_client.const import (
    AddressTupleVXType,
    DeviceOrServiceType,
    IPvXAddress,
    NotificationSubType,
    NotificationType,
    SearchTarget,
    SsdpHeaders,
    SsdpSource,
    UniqueDeviceName,
)
from async_upnp_client.search import SsdpSearchListener
from async_upnp_client.ssdp import SSDP_MX, determine_source_target, udn_from_headers
from async_upnp_client.utils import CaseInsensitiveDict

_LOGGER = logging.getLogger(__name__)
CACHE_CONTROL_RE = re.compile(r"max-age\s*=\s*(\d+)", re.IGNORECASE)
DEFAULT_MAX_AGE = timedelta(seconds=900)
IGNORED_HEADERS = {
    "date",
    "cache-control",
    "server",
    "location",  # Location-header is handled differently!
}


def valid_search_headers(headers: SsdpHeaders) -> bool:
    """Validate if this search is usable."""
    # pylint: disable=invalid-name
    udn = headers.get("_udn")  # type: Optional[str]
    st = headers.get("st")  # type: Optional[str]
    location = headers.get("location", "")  # type: str
    return bool(
        udn
        and st
        and location
        and location.startswith("http")
        and not (
            "://127.0.0.1" in location
            or "://[::1]" in location
            or "://169.254" in location
        )
    )


def valid_advertisement_headers(headers: SsdpHeaders) -> bool:
    """Validate if this advertisement is usable for connecting to a device."""
    # pylint: disable=invalid-name
    udn = headers.get("_udn")  # type: Optional[str]
    nt = headers.get("nt")  # type: Optional[str]
    nts = headers.get("nts")  # type: Optional[str]
    location = headers.get("location", "")  # type: str
    return bool(
        udn
        and nt
        and nts
        and location
        and location.startswith("http")
        and not (
            "://127.0.0.1" in location
            or "://[::1]" in location
            or "://169.254" in location
        )
    )


def valid_byebye_headers(headers: SsdpHeaders) -> bool:
    """Validate if this advertisement has required headers for byebye."""
    # pylint: disable=invalid-name
    udn = headers.get("_udn")  # type: Optional[str]
    nt = headers.get("nt")  # type: Optional[str]
    nts = headers.get("nts")  # type: Optional[str]
    return bool(udn and nt and nts)


def extract_valid_to(headers: SsdpHeaders) -> datetime:
    """Extract/create valid to."""
    cache_control = headers.get("cache-control", "")
    match = CACHE_CONTROL_RE.search(cache_control)
    if match:
        max_age = int(match[1])
        uncache_after = timedelta(seconds=max_age)
    else:
        uncache_after = DEFAULT_MAX_AGE
    timestamp: datetime = headers["_timestamp"]
    return timestamp + uncache_after


class SsdpDevice:
    """
    SSDP Device.

    Holds all known information about the device.
    """

    # pylint: disable=too-many-instance-attributes

    def __init__(self, udn: str, valid_to: datetime):
        """Initialize."""
        self.udn = udn
        self.valid_to: datetime = valid_to
        self._locations: Dict[str, datetime] = {}
        self.last_seen: Optional[datetime] = None
        self.search_headers: dict[DeviceOrServiceType, CaseInsensitiveDict] = {}
        self.advertisement_headers: dict[DeviceOrServiceType, CaseInsensitiveDict] = {}
        self.userdata: Any = None

    def add_location(self, location: str, valid_to: datetime) -> None:
        """Add a (new) location the device can be reached at."""
        self._locations[location] = valid_to

    @property
    def location(self) -> Optional[str]:
        """
        Get a location of the device.

        Kept for compatibility, use method `locations`.
        """
        # Sort such that the same location will be given each time.
        for location in sorted(self.locations):
            return location

        return None

    @property
    def locations(self) -> Set[str]:
        """Get all know locations of the device."""
        self.purge_locations()
        return set(self._locations.keys())

    def purge_locations(self) -> None:
        """Purge locations which are no longer valid/timed out."""
        now = datetime.now()
        to_remove = [
            location for location, valid_to in self._locations.items() if now > valid_to
        ]
        for location in to_remove:
            del self._locations[location]

    def combined_headers(
        self,
        device_or_service_type: DeviceOrServiceType,
    ) -> SsdpHeaders:
        """Get headers from search and advertisement for a given device- or service type."""
        if device_or_service_type in self.search_headers:
            headers = {**self.search_headers[device_or_service_type].as_dict()}
        else:
            headers = {}
        if device_or_service_type in self.advertisement_headers:
            headers.update(self.advertisement_headers[device_or_service_type].as_dict())
        if "_source" in headers:
            del headers["_source"]
        return CaseInsensitiveDict(headers)

    @property
    def all_combined_headers(self) -> Mapping[DeviceOrServiceType, SsdpHeaders]:
        """Get all headers from search and advertisement for all known device- and service types."""
        dsts = set(self.advertisement_headers).union(set(self.search_headers))
        return {dst: self.combined_headers(dst) for dst in dsts}

    def __repr__(self) -> str:
        """Return the representation."""
        return f"<{type(self).__name__}({self.udn})>"


def same_headers_differ(
    current_headers: CaseInsensitiveDict, new_headers: SsdpHeaders
) -> bool:
    """Compare headers present in both to see if anything interesting has changed."""
    for header, current_value in current_headers.as_dict().items():
        header_lowered = header.lower()
        if header.startswith("_") or header_lowered in IGNORED_HEADERS:
            continue
        new_value = new_headers.get(header)
        if new_value is None:
            continue
        if current_value != new_value:
            _LOGGER.debug(
                "Header %s changed from %s to %s", header, current_value, new_value
            )
            return True
    return False


def headers_differ_from_existing_advertisement(
    ssdp_device: SsdpDevice, dst: DeviceOrServiceType, headers: SsdpHeaders
) -> bool:
    """Compare against existing advertisement headers to see if anything interesting has changed."""
    if dst not in ssdp_device.advertisement_headers:
        return False
    headers_old = ssdp_device.advertisement_headers[dst]
    return same_headers_differ(headers_old, headers)


def headers_differ_from_existing_search(
    ssdp_device: SsdpDevice, dst: DeviceOrServiceType, headers: SsdpHeaders
) -> bool:
    """Compare against existing search headers to see if anything interesting has changed."""
    if dst not in ssdp_device.search_headers:
        return False
    headers_old = ssdp_device.search_headers[dst]
    return same_headers_differ(headers_old, headers)


def same_ip_version(new_host_ip: IPvXAddress, location: str) -> bool:
    """Test if location points to a host with the same IP version."""
    parts = urlparse(location)
    host = parts.hostname
    host_ip: IPvXAddress = ip_address(host)
    return host_ip.version == new_host_ip.version


def location_changed(ssdp_device: SsdpDevice, headers: SsdpHeaders) -> bool:
    """Test if location changed for device."""
    new_location = headers.get("location", "")
    if not new_location:
        return False

    # Device did not have any location, must be new.
    locations = ssdp_device.locations
    if not locations:
        return True

    # Ensure the new location is parsable.
    try:
        new_host = urlparse(new_location).hostname
        new_host_ip = ip_address(new_host)
    except ValueError:
        return False

    for location in ssdp_device.locations:
        try:
            # Only test existing locations using the same IP version (IPv4/IPv6.)
            if not same_ip_version(new_host_ip, location):
                continue

            if location != new_location:
                return True
        except ValueError:
            pass

    return False


class SsdpDeviceTracker(AbstractAsyncContextManager):
    """
    Device tracker.

    Tracks `SsdpDevices` seen by the `SsdpListener`. Can be shared between `SsdpListeners`.

    This uses a `asyncio.Lock` to prevent simulatinous device updates when the `SsdpDeviceTracker`
    is shared between `SsdpListeners` (e.g., for simultaneous IPv4 and IPv6 handling
    on the same network.)
    """

    def __init__(self) -> None:
        """Initialize."""
        self.devices: dict[UniqueDeviceName, SsdpDevice] = {}
        self.next_valid_to: Optional[datetime] = None
        self._lock = Lock()

    async def __aenter__(self) -> "SsdpDeviceTracker":
        """Acquire the lock."""
        await self._lock.acquire()
        return self

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_value: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> None:
        """Release the lock."""
        self._lock.release()

    def see_search(
        self, headers: SsdpHeaders
    ) -> Tuple[
        bool, Optional[SsdpDevice], Optional[DeviceOrServiceType], Optional[SsdpSource]
    ]:
        """See a device through a search."""
        assert self._lock.locked(), "Lock first"

        if not valid_search_headers(headers):
            _LOGGER.debug("Received invalid search headers: %s", headers)
            return False, None, None, None

        udn = headers["_udn"]
        is_new_device = udn not in self.devices

        ssdp_device, new_location = self._see_device(headers)
        if not ssdp_device:
            return False, None, None, None

        search_target: SearchTarget = headers["ST"]
        is_new_service = (
            search_target not in ssdp_device.advertisement_headers
            and search_target not in ssdp_device.search_headers
        )
        if is_new_service:
            _LOGGER.debug("See new service: %s, type: %s", ssdp_device, search_target)

        changed = (
            is_new_device
            or is_new_service
            or headers_differ_from_existing_search(ssdp_device, search_target, headers)
            or headers_differ_from_existing_advertisement(
                ssdp_device, search_target, headers
            )
            or new_location
        )
        ssdp_source = SsdpSource.SEARCH_CHANGED if changed else SsdpSource.SEARCH_ALIVE

        # Update stored headers.
        if search_target in ssdp_device.search_headers:
            ssdp_device.search_headers[search_target].replace(headers)
        else:
            ssdp_device.search_headers[search_target] = CaseInsensitiveDict(headers)

        return True, ssdp_device, search_target, ssdp_source

    def see_advertisement(
        self, headers: SsdpHeaders
    ) -> Tuple[bool, Optional[SsdpDevice], Optional[DeviceOrServiceType]]:
        """See a device through an advertisement."""
        assert self._lock.locked(), "Lock first"

        if not valid_advertisement_headers(headers):
            _LOGGER.debug("Received invalid advertisement headers: %s", headers)
            return False, None, None

        udn = headers["_udn"]
        is_new_device = udn not in self.devices

        ssdp_device, new_location = self._see_device(headers)
        if not ssdp_device:
            return False, None, None

        notification_type: NotificationType = headers["NT"]
        is_new_service = (
            notification_type not in ssdp_device.advertisement_headers
            and notification_type not in ssdp_device.search_headers
        )
        if is_new_service:
            _LOGGER.debug(
                "See new service: %s, type: %s", ssdp_device, notification_type
            )

        notification_sub_type: NotificationSubType = headers["NTS"]
        propagate = (
            notification_sub_type == NotificationSubType.SSDP_UPDATE
            or is_new_device
            or is_new_service
            or headers_differ_from_existing_advertisement(
                ssdp_device, notification_type, headers
            )
            or headers_differ_from_existing_search(
                ssdp_device, notification_type, headers
            )
            or new_location
        )

        # Update stored headers.
        if notification_type in ssdp_device.advertisement_headers:
            ssdp_device.advertisement_headers[notification_type].replace(headers)
        else:
            ssdp_device.advertisement_headers[notification_type] = CaseInsensitiveDict(
                headers
            )

        return propagate, ssdp_device, notification_type

    def _see_device(self, headers: SsdpHeaders) -> Tuple[Optional[SsdpDevice], bool]:
        """See a device through a search or advertisement."""
        # Purge any old devices.
        self.purge_devices()

        udn = udn_from_headers(headers)
        if not udn:
            # Ignore broken devices.
            return None, False

        valid_to = extract_valid_to(headers)

        if udn not in self.devices:
            # Create new device.
            ssdp_device = SsdpDevice(udn, valid_to)
            _LOGGER.debug("See new device: %s", ssdp_device)
            self.devices[udn] = ssdp_device
        else:
            ssdp_device = self.devices[udn]
            ssdp_device.valid_to = valid_to

        # Test if new location.
        new_location = location_changed(ssdp_device, headers)

        # Update device.
        ssdp_device.add_location(headers["location"], valid_to)
        ssdp_device.last_seen = headers["_timestamp"]
        if not self.next_valid_to or self.next_valid_to > ssdp_device.valid_to:
            self.next_valid_to = ssdp_device.valid_to

        return ssdp_device, new_location

    def unsee_advertisement(
        self, headers: SsdpHeaders
    ) -> Tuple[bool, Optional[SsdpDevice], Optional[DeviceOrServiceType]]:
        """Remove a device through an advertisement."""
        assert self._lock.locked(), "Lock first"

        if not valid_byebye_headers(headers):
            return False, None, None

        udn = udn_from_headers(headers)
        if not udn:
            # Ignore broken devices.
            return False, None, None

        if udn not in self.devices:
            return False, None, None

        ssdp_device = self.devices[udn]
        del self.devices[udn]

        # Update device before propagating it
        notification_type: NotificationType = headers["NT"]
        if notification_type in ssdp_device.advertisement_headers:
            ssdp_device.advertisement_headers[notification_type].replace(headers)
        else:
            ssdp_device.advertisement_headers[notification_type] = CaseInsensitiveDict(
                headers
            )

        propagate = True  # Always true, if this is the 2nd unsee then device is already deleted.
        return propagate, ssdp_device, notification_type

    def get_device(self, headers: SsdpHeaders) -> Optional[SsdpDevice]:
        """Get a device from headers."""
        if "usn" not in headers:
            return None

        udn = udn_from_headers(headers)
        if not udn:
            return None

        return self.devices.get(udn)

    def purge_devices(self, override_now: Optional[datetime] = None) -> None:
        """Purge any devices for which the CACHE-CONTROL header is timed out."""
        now = override_now or datetime.now()
        if self.next_valid_to and self.next_valid_to > now:
            return
        self.next_valid_to = None
        to_remove = []
        for usn, device in self.devices.items():
            if now > device.valid_to:
                to_remove.append(usn)
            elif not self.next_valid_to or device.valid_to < self.next_valid_to:
                self.next_valid_to = device.valid_to
                device.purge_locations()
        for usn in to_remove:
            _LOGGER.debug("Purging device, USN: %s", usn)
            del self.devices[usn]


class SsdpListener:
    """SSDP Search and Advertisement listener."""

    # pylint: disable=too-many-instance-attributes

    def __init__(
        self,
        async_callback: Callable[
            [SsdpDevice, DeviceOrServiceType, SsdpSource], Awaitable
        ],
        source: Optional[AddressTupleVXType] = None,
        target: Optional[AddressTupleVXType] = None,
        loop: Optional[AbstractEventLoop] = None,
        search_timeout: int = SSDP_MX,
        device_tracker: Optional[SsdpDeviceTracker] = None,
    ) -> None:
        """Initialize."""
        # pylint: disable=too-many-arguments
        self.async_callback = async_callback
        self.source, self.target = determine_source_target(source, target)
        self.loop = loop
        self.search_timeout = search_timeout
        self._device_tracker = device_tracker or SsdpDeviceTracker()
        self._advertisement_listener: Optional[SsdpAdvertisementListener] = None
        self._search_listener: Optional[SsdpSearchListener] = None

    async def async_start(self) -> None:
        """Start search listener/advertisement listener."""
        self._advertisement_listener = SsdpAdvertisementListener(
            on_alive=self._on_alive,
            on_update=self._on_update,
            on_byebye=self._on_byebye,
            source=self.source,
            target=self.target,
            loop=self.loop,
        )
        await self._advertisement_listener.async_start()

        self._search_listener = SsdpSearchListener(
            self._on_search,
            loop=self.loop,
            source=self.source,
            target=self.target,
            timeout=self.search_timeout,
        )
        await self._search_listener.async_start()

    async def async_stop(self) -> None:
        """Stop scanner/listener."""
        if self._advertisement_listener:
            await self._advertisement_listener.async_stop()

        if self._search_listener:
            self._search_listener.async_stop()

    async def async_search(
        self, override_target: Optional[AddressTupleVXType] = None
    ) -> None:
        """Send a SSDP Search packet."""
        assert self._search_listener is not None, "Call async_start() first"
        self._search_listener.async_search(override_target)

    async def _on_search(self, headers: SsdpHeaders) -> None:
        """Search callback."""
        async with self._device_tracker:
            (
                propagate,
                ssdp_device,
                device_or_service_type,
                ssdp_source,
            ) = self._device_tracker.see_search(headers)

            if propagate and ssdp_device and device_or_service_type:
                assert ssdp_source is not None
                await self.async_callback(
                    ssdp_device, device_or_service_type, ssdp_source
                )

    async def _on_alive(self, headers: SsdpHeaders) -> None:
        """On alive."""
        async with self._device_tracker:
            (
                propagate,
                ssdp_device,
                device_or_service_type,
            ) = self._device_tracker.see_advertisement(headers)

            if propagate and ssdp_device and device_or_service_type:
                await self.async_callback(
                    ssdp_device, device_or_service_type, SsdpSource.ADVERTISEMENT_ALIVE
                )

    async def _on_byebye(self, headers: SsdpHeaders) -> None:
        """On byebye."""
        async with self._device_tracker:
            (
                propagate,
                ssdp_device,
                device_or_service_type,
            ) = self._device_tracker.unsee_advertisement(headers)

            if propagate and ssdp_device and device_or_service_type:
                await self.async_callback(
                    ssdp_device, device_or_service_type, SsdpSource.ADVERTISEMENT_BYEBYE
                )

    async def _on_update(self, headers: SsdpHeaders) -> None:
        """On update."""
        async with self._device_tracker:
            (
                propagate,
                ssdp_device,
                device_or_service_type,
            ) = self._device_tracker.see_advertisement(headers)

            if propagate and ssdp_device and device_or_service_type:
                await self.async_callback(
                    ssdp_device, device_or_service_type, SsdpSource.ADVERTISEMENT_UPDATE
                )

    @property
    def devices(self) -> Mapping[str, SsdpDevice]:
        """Get the known devices."""
        return self._device_tracker.devices
