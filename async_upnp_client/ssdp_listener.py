"""SSDP Search + Advertisement listener, keeping track of known devices on the network."""

import logging
import re
from asyncio.events import AbstractEventLoop
from datetime import datetime, timedelta
from ipaddress import ip_address
from typing import Any, Awaitable, Callable, Mapping, Optional, Tuple

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
from async_upnp_client.ssdp import SSDP_IP_V4, SSDP_MX, SSDP_PORT, udn_from_headers
from async_upnp_client.utils import CaseInsensitiveDict

_LOGGER = logging.getLogger(__name__)
CACHE_CONTROL_RE = re.compile(r"max-age\s*=\s*(\d+)")
DEFAULT_MAX_AGE = timedelta(seconds=900)
IGNORED_HEADERS = {
    "date",
    "cache-control",
    "server",
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
        and not ("://127.0.0.1" in location or "://[::1]" in location)
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
        and not ("://127.0.0.1" in location or "://[::1]" in location)
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
        self.location: Optional[str] = None
        self.last_seen: Optional[datetime] = None
        self.search_headers: dict[DeviceOrServiceType, CaseInsensitiveDict] = {}
        self.advertisement_headers: dict[DeviceOrServiceType, CaseInsensitiveDict] = {}
        self.userdata: Any = None

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
        if header.startswith("_") or header.lower() in IGNORED_HEADERS:
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
    return same_headers_differ(ssdp_device.advertisement_headers[dst], headers)


def headers_differ_from_existing_search(
    ssdp_device: SsdpDevice, dst: DeviceOrServiceType, headers: SsdpHeaders
) -> bool:
    """Compare against existing search headers to see if anything interesting has changed."""
    if dst not in ssdp_device.search_headers:
        return False
    return same_headers_differ(ssdp_device.search_headers[dst], headers)


class SsdpDeviceTracker:
    """Device tracker."""

    def __init__(self) -> None:
        """Initialize."""
        self.devices: dict[UniqueDeviceName, SsdpDevice] = {}
        self.next_valid_to: Optional[datetime] = None

    def see_search(
        self, headers: SsdpHeaders
    ) -> Tuple[
        bool, Optional[SsdpDevice], Optional[DeviceOrServiceType], Optional[SsdpSource]
    ]:
        """See a device through a search."""
        if not valid_search_headers(headers):
            _LOGGER.debug("Received invalid search headers: %s", headers)
            return False, None, None, None

        udn = headers["_udn"]
        is_new_device = udn not in self.devices

        ssdp_device = self._see_device(headers)
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
        if not valid_advertisement_headers(headers):
            _LOGGER.debug("Received invalid advertisement headers: %s", headers)
            return False, None, None

        udn = headers["_udn"]
        is_new_device = udn not in self.devices

        ssdp_device = self._see_device(headers)
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
        )

        # Update stored headers.
        if notification_type in ssdp_device.advertisement_headers:
            ssdp_device.advertisement_headers[notification_type].replace(headers)
        else:
            ssdp_device.advertisement_headers[notification_type] = CaseInsensitiveDict(
                headers
            )

        return propagate, ssdp_device, notification_type

    def _see_device(self, headers: SsdpHeaders) -> Optional[SsdpDevice]:
        """See a device through a search."""
        # Purge any old devices.
        self.purge_devices()

        udn = udn_from_headers(headers)
        if not udn:
            # Ignore broken devices.
            return None

        valid_to = extract_valid_to(headers)

        if udn not in self.devices:
            # Create new device.
            ssdp_device = SsdpDevice(udn, valid_to)
            _LOGGER.debug("See new device: %s", ssdp_device)
            self.devices[udn] = ssdp_device
        else:
            ssdp_device = self.devices[udn]
            ssdp_device.valid_to = valid_to

        # Update device.
        ssdp_device.location = headers["location"]
        ssdp_device.last_seen = headers["_timestamp"]
        if not self.next_valid_to or self.next_valid_to > ssdp_device.valid_to:
            self.next_valid_to = ssdp_device.valid_to

        return ssdp_device

    def unsee_advertisement(
        self, headers: SsdpHeaders
    ) -> Tuple[bool, Optional[SsdpDevice], Optional[DeviceOrServiceType]]:
        """Remove a device through an advertisement."""
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
        source_ip: Optional[IPvXAddress] = None,
        target: Optional[AddressTupleVXType] = None,
        loop: Optional[AbstractEventLoop] = None,
        search_timeout: int = SSDP_MX,
    ) -> None:
        """Initialize."""
        # pylint: disable=too-many-arguments
        self.async_callback = async_callback
        self.source_ip = source_ip
        self.target: AddressTupleVXType = target or (
            SSDP_IP_V4,
            SSDP_PORT,
        )
        self.loop = loop
        self.search_timeout = search_timeout
        self._device_tracker = SsdpDeviceTracker()
        self._advertisement_listener: Optional[SsdpAdvertisementListener] = None
        self._search_listener: Optional[SsdpSearchListener] = None

    async def async_start(self) -> None:
        """Start search listener/advertisement listener."""
        target_ip = ip_address(self.target[0])
        self._advertisement_listener = SsdpAdvertisementListener(
            on_alive=self._on_alive,
            on_update=self._on_update,
            on_byebye=self._on_byebye,
            source_ip=self.source_ip,
            target_ip=target_ip,
            loop=self.loop,
        )
        await self._advertisement_listener.async_start()

        self._search_listener = SsdpSearchListener(
            self._on_search,
            loop=self.loop,
            source_ip=self.source_ip,
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
        (
            propagate,
            ssdp_device,
            device_or_service_type,
            ssdp_source,
        ) = self._device_tracker.see_search(headers)

        if propagate and ssdp_device and device_or_service_type:
            assert ssdp_source is not None
            await self.async_callback(ssdp_device, device_or_service_type, ssdp_source)

    async def _on_alive(self, headers: SsdpHeaders) -> None:
        """On alive."""
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
