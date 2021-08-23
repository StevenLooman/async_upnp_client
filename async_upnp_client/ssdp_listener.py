"""SSDP Search + Advertisement listener, keeping track of known devices on the network."""

import enum
import logging
import re
from asyncio.events import AbstractEventLoop
from datetime import datetime, timedelta
from ipaddress import ip_address
from typing import (
    Any,
    Awaitable,
    Callable,
    Mapping,
    MutableMapping,
    Optional,
    Tuple,
    Union,
)

from async_upnp_client.advertisement import SsdpAdvertisementListener
from async_upnp_client.const import (
    AddressTupleVXType,
    IPvXAddress,
    NotificationSubType,
    NotificationType,
    SearchTarget,
    UniqueDeviceName,
)
from async_upnp_client.search import SsdpSearchListener
from async_upnp_client.ssdp import SSDP_IP_V4, SSDP_MX, SSDP_PORT, udn_from_headers
from async_upnp_client.utils import CaseInsensitiveDict

_LOGGER = logging.getLogger(__name__)
CACHE_CONTROL_RE = re.compile(r"max-age\s*=\s*(\d+)")
DEFAULT_MAX_AGE = timedelta(seconds=900)


@enum.unique
class SourceType(enum.Enum):
    """Source of change."""

    SEARCH = 0
    ALIVE = 1
    UPDATED = 2
    BYEBYE = 3


def valid_search_headers(headers: Mapping[str, Any]) -> bool:
    """Validate if this search is usable."""
    return "usn" in headers and "st" in headers


def valid_advertisement_headers(headers: Mapping[str, Any]) -> bool:
    """Validate if this advertisement is usable."""
    return "usn" in headers and "nt" in headers and "nts" in headers


def extract_valid_to(headers: Mapping[str, Any]) -> datetime:
    """Extract/create valid to."""
    match = CACHE_CONTROL_RE.search(headers.get("cache-controle", ""))
    if match:
        max_age = int(match[1])
        uncache_after = timedelta(seconds=max_age)
    else:
        uncache_after = DEFAULT_MAX_AGE
    return datetime.now() + uncache_after


def headers_differ(
    current_headers: Mapping[str, Any], new_headers: Mapping[str, Any]
) -> bool:
    """Compare headers to see if anything interesting has changed."""
    current_filtered = {
        key: value
        for key, value in current_headers.items()
        if not key.startswith("_") and key.lower() != "date"
    }
    new_filtered = {
        key: value
        for key, value in new_headers.items()
        if not key.startswith("_") and key.lower() != "date"
    }
    if _LOGGER.level <= logging.DEBUG:
        diff_values = {
            k: (
                current_filtered.get(k),
                new_filtered.get(k),
            )
            for k in set(current_filtered).union(set(new_filtered))
            if current_filtered.get(k) != new_filtered.get(k)
        }
        if current_filtered and diff_values:
            _LOGGER.debug("Changed values: %s", diff_values)
    return current_filtered != new_filtered


class SsdpDevice:
    """
    SSDP Device.

    Holds all known information about the device.
    """

    # pylint: disable=too-many-instance-attributes

    def __init__(
        self,
        udn: str,
    ):
        """Initialize."""
        self.udn = udn
        self.location: Optional[str] = None
        self.last_seen: Optional[datetime] = None
        self.valid_to: Optional[datetime] = None
        self.device_types: set[str] = set()
        self.service_types: set[str] = set()
        self.search_headers: dict[NotificationType, CaseInsensitiveDict] = {}
        self.advertisement_headers: dict[NotificationType, CaseInsensitiveDict] = {}
        self.userdata: Any = None

    def combined_headers(
        self,
        notification_type: Union[NotificationType, SearchTarget],
    ) -> Mapping[str, Any]:
        """Get combined headers from search and advertisement for a given NT."""
        headers = dict(self.search_headers.get(notification_type, {}))
        headers.update(self.advertisement_headers.get(notification_type, {}))
        return headers

    def __repr__(self) -> str:
        """Return the representation."""
        return f"<{type(self).__name__}({self.udn})>"


def headers_differ_from_existing_advertisement(
    ssdp_device: SsdpDevice, key: str, headers: Mapping[str, Any]
) -> bool:
    """Compare against existing search headers to see if anything interesting has changed."""
    if key not in ssdp_device.advertisement_headers:
        return False

    current_headers = ssdp_device.advertisement_headers[key]
    shared_keys = set(current_headers) - set(headers)

    current_filtered = {
        key: value for key, value in current_headers.items() if key in shared_keys
    }
    new_filtered = {key: value for key, value in headers.items() if key in shared_keys}
    return headers_differ(current_filtered, new_filtered)


def headers_differ_from_existing_search(
    ssdp_device: SsdpDevice, key: str, headers: Mapping[str, Any]
) -> bool:
    """Compare against existing search headers to see if anything interesting has changed."""
    if key not in ssdp_device.search_headers:
        return False

    current_headers = ssdp_device.search_headers[key]
    shared_keys = set(current_headers).intersection(set(headers))

    current_filtered = {
        key: value for key, value in current_headers.items() if key in shared_keys
    }
    new_filtered = {key: value for key, value in headers.items() if key in shared_keys}
    return headers_differ(current_filtered, new_filtered)


class SsdpDeviceTracker:
    """Device tracker."""

    def __init__(self) -> None:
        """Initialize."""
        self.devices: dict[UniqueDeviceName, SsdpDevice] = {}

    def see_search(
        self, headers: Mapping[str, Any]
    ) -> Tuple[bool, Optional[SsdpDevice], Optional[SearchTarget]]:
        """See a device through a search."""
        if not valid_search_headers(headers):
            return False, None, None

        udn = headers["_udn"]
        is_new_device = udn not in self.devices

        ssdp_device = self._see_device(headers)
        if not ssdp_device:
            return False, None, None

        search_target = headers["ST"]
        propagate = (
            is_new_device
            or headers_differ_from_existing_search(ssdp_device, search_target, headers)
            or headers_differ_from_existing_advertisement(
                ssdp_device, search_target, headers
            )
        )

        # Update stored headers.
        current_headers = ssdp_device.search_headers.setdefault(
            search_target, CaseInsensitiveDict()
        )
        current_headers.clear()
        current_headers.update(headers)

        return propagate, ssdp_device, search_target

    def see_advertisement(
        self, headers: Mapping[str, Any]
    ) -> Tuple[bool, Optional[SsdpDevice], Optional[NotificationType]]:
        """See a device through an advertisement."""
        if not valid_advertisement_headers(headers):
            return False, None, None

        udn = headers["_udn"]
        is_new_device = udn not in self.devices

        ssdp_device = self._see_device(headers)
        if not ssdp_device:
            return False, None, None

        notification_type = headers["NT"]
        notification_sub_type = headers["NTS"]
        propagate = (
            notification_sub_type == NotificationSubType.SSDP_UPDATE
            or is_new_device
            or headers_differ_from_existing_advertisement(
                ssdp_device, notification_type, headers
            )
            or headers_differ_from_existing_search(
                ssdp_device, notification_type, headers
            )
        )

        # Update stored headers.
        current_headers = ssdp_device.advertisement_headers.setdefault(
            notification_type, CaseInsensitiveDict()
        )
        current_headers.clear()
        current_headers.update(headers)

        return propagate, ssdp_device, notification_type

    def _see_device(self, headers: Mapping[str, Any]) -> Optional[SsdpDevice]:
        """See a device through a search."""
        udn = udn_from_headers(headers)
        if not udn:
            # Ignore broken devices.
            return None

        if udn not in self.devices:
            # Create new device.
            ssdp_device = SsdpDevice(udn)
            _LOGGER.debug("See new device: %s", ssdp_device)
            self.devices[udn] = ssdp_device
        ssdp_device = self.devices[udn]

        # Update device.
        ssdp_device.location = headers["location"]
        ssdp_device.last_seen = headers["_timestamp"]
        ssdp_device.valid_to = extract_valid_to(headers)

        # Purge any old devices.
        self.purge_devices()

        return ssdp_device

    def unsee_advertisement(
        self, headers: Mapping[str, Any]
    ) -> Tuple[bool, Optional[SsdpDevice], Optional[NotificationType]]:
        """Remove a device through an advertisement."""
        if not valid_advertisement_headers(headers):
            return False, None, None

        udn = udn_from_headers(headers)
        if not udn:
            # Ignore broken devices.
            return False, None, None

        if udn not in self.devices:
            return False, None, None

        ssdp_device = self.devices[udn]
        del self.devices[udn]

        propagate = True  # Always true, if this is the 2nd unsee then device is already deleted.
        notification_type = headers["NT"]
        return propagate, ssdp_device, notification_type

    def get_device(self, headers: Mapping[str, Any]) -> Optional[SsdpDevice]:
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
        to_remove = [
            usn
            for usn, device in self.devices.items()
            if device.valid_to and now > device.valid_to
        ]
        for usn in to_remove:
            del self.devices[usn]


class SsdpListener:
    """SSDP Search and Advertisement listener."""

    # pylint: disable=too-many-instance-attributes

    def __init__(
        self,
        callback: Callable[
            [SsdpDevice, Union[NotificationType, SearchTarget], SourceType], Awaitable
        ],
        source_ip: Optional[IPvXAddress] = None,
        target: Optional[AddressTupleVXType] = None,
        loop: Optional[AbstractEventLoop] = None,
        search_timeout: int = SSDP_MX,
    ) -> None:
        """Initialize."""
        # pylint: disable=too-many-arguments
        self.callback = callback
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

    def async_search(
        self, override_target: Optional[AddressTupleVXType] = None
    ) -> None:
        """Send a SSDP Search packet."""
        assert self._search_listener is not None, "Call async_start() first"
        self._search_listener.async_search(override_target)

    async def _on_search(self, headers: MutableMapping[str, str]) -> None:
        """Search callback."""
        propagate, ssdp_device, search_target = self._device_tracker.see_search(headers)

        if propagate and ssdp_device and search_target:
            await self.callback(ssdp_device, search_target, SourceType.SEARCH)

    async def _on_alive(self, headers: MutableMapping[str, str]) -> None:
        """On alive."""
        (
            propagate,
            ssdp_device,
            notification_type,
        ) = self._device_tracker.see_advertisement(headers)

        if propagate and ssdp_device and notification_type:
            await self.callback(ssdp_device, notification_type, SourceType.ALIVE)

    async def _on_byebye(self, headers: MutableMapping[str, str]) -> None:
        """On byebye."""
        (
            propagate,
            ssdp_device,
            notification_type,
        ) = self._device_tracker.unsee_advertisement(headers)

        if propagate and ssdp_device and notification_type:
            await self.callback(ssdp_device, notification_type, SourceType.BYEBYE)

    async def _on_update(self, headers: MutableMapping[str, str]) -> None:
        """On update."""
        (
            propagate,
            ssdp_device,
            notification_type,
        ) = self._device_tracker.see_advertisement(headers)

        if propagate and ssdp_device and notification_type:
            await self.callback(ssdp_device, notification_type, SourceType.UPDATED)

    @property
    def devices(self) -> Mapping[str, SsdpDevice]:
        """Get the known devices."""
        return self._device_tracker.devices
