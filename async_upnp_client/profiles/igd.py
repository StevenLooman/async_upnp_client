# -*- coding: utf-8 -*-
"""async_upnp_client.profiles.igd module."""

import asyncio
import logging
from datetime import datetime, timedelta
from ipaddress import IPv4Address
from typing import List, NamedTuple, Optional, Sequence, Union

from async_upnp_client.client import UpnpAction, UpnpDevice
from async_upnp_client.event_handler import UpnpEventHandler
from async_upnp_client.profiles.profile import UpnpProfileDevice

TIMESTAMP = "timestamp"
BYTES_RECEIVED = "bytes_received"
BYTES_SENT = "bytes_sent"
PACKETS_RECEIVED = "packets_received"
PACKETS_SENT = "packets_sent"
KIBIBYTES_PER_SEC_RECEIVED = "kibytes_sec_received"
KIBIBYTES_PER_SEC_SENT = "kibytes_sec_sent"
PACKETS_SEC_RECEIVED = "packets_sec_received"
PACKETS_SEC_SENT = "packets_sec_sent"
STATUS_INFO = "status_info"
EXTERNAL_IP_ADDRESS = "external_ip_address"

_LOGGER = logging.getLogger(__name__)


class CommonLinkProperties(NamedTuple):
    """Common link properties."""

    wan_access_type: str
    layer1_upstream_max_bit_rate: int
    layer1_downstream_max_bit_rate: int
    physical_link_status: str


class ConnectionTypeInfo(NamedTuple):
    """Connection type info."""

    connection_type: str
    possible_connection_types: str


class StatusInfo(NamedTuple):
    """Status info."""

    connection_status: str
    last_connection_error: str
    uptime: int


class NatRsipStatusInfo(NamedTuple):
    """NAT RSIP status info."""

    nat_enabled: bool
    rsip_available: bool


class PortMappingEntry(NamedTuple):
    """Port mapping entry."""

    remote_host: Optional[IPv4Address]
    external_port: int
    protocol: str
    internal_port: int
    internal_client: IPv4Address
    enabled: bool
    description: str
    lease_duration: Optional[timedelta]


class TrafficCounterState(NamedTuple):
    """Traffic state."""

    timestamp: datetime
    bytes_received: Union[None, Exception, int]
    bytes_sent: Union[None, Exception, int]
    packets_received: Union[None, Exception, int]
    packets_sent: Union[None, Exception, int]


class IgdState(NamedTuple):
    """IGD state."""

    timestamp: datetime
    bytes_received: Union[None, Exception, int]
    bytes_sent: Union[None, Exception, int]
    packets_received: Union[None, Exception, int]
    packets_sent: Union[None, Exception, int]
    status_info: Union[None, Exception, StatusInfo]
    external_ip_address: Union[str, Exception, None]

    # Derived values.
    kibibytes_per_sec_received: Union[None, float]
    kibibytes_per_sec_sent: Union[None, float]
    packets_per_sec_received: Union[None, float]
    packets_per_sec_sent: Union[None, float]


def _derive_value_per_second(
    value_name: str,
    current_timestamp: datetime,
    current_value: Union[None, Exception, int],
    last_timestamp: Union[None, Exception, datetime],
    last_value: Union[None, Exception, int],
) -> Union[None, float]:
    """Calculate average based on current and last value."""
    if (
        last_timestamp is None
        or isinstance(current_value, Exception)
        or current_value is None
        or isinstance(last_value, Exception)
        or last_value is None
    ):
        return None

    assert isinstance(last_timestamp, datetime)
    assert isinstance(last_value, int)
    if last_value > current_value:
        # Value has overflowed, don't try to calculate anything.
        return None

    delta_time = current_timestamp - last_timestamp
    delta_value: Union[int, float] = current_value - last_value
    if value_name in (BYTES_RECEIVED, BYTES_SENT):
        delta_value = delta_value / 1024  # 1KB
    return delta_value / delta_time.total_seconds()


class IgdDevice(UpnpProfileDevice):
    """Representation of a IGD device."""

    # pylint: disable=too-many-public-methods

    DEVICE_TYPES = [
        "urn:schemas-upnp-org:device:InternetGatewayDevice:1",
        "urn:schemas-upnp-org:device:InternetGatewayDevice:2",
    ]

    _SERVICE_TYPES = {
        "WANPPPC": {
            "urn:schemas-upnp-org:service:WANPPPConnection:1",
        },
        "WANIPC": {
            "urn:schemas-upnp-org:service:WANIPConnection:1",
        },
        "WANCIC": {
            "urn:schemas-upnp-org:service:WANCommonInterfaceConfig:1",
        },
        "L3FWD": {
            "urn:schemas-upnp-org:service:Layer3Forwarding:1",
        },
    }

    def __init__(
        self, device: UpnpDevice, event_handler: Optional[UpnpEventHandler]
    ) -> None:
        """Initialize."""
        super().__init__(device, event_handler)

        self._last_traffic_state = TrafficCounterState(
            timestamp=datetime.now(),
            bytes_received=None,
            bytes_sent=None,
            packets_received=None,
            packets_sent=None,
        )

    def _any_action(
        self, service_names: Sequence[str], action_name: str
    ) -> Optional[UpnpAction]:
        for service_name in service_names:
            action = self._action(service_name, action_name)
            if action is not None:
                return action
        return None

    async def async_get_total_bytes_received(self) -> Optional[int]:
        """Get total bytes received."""
        action = self._action("WANCIC", "GetTotalBytesReceived")
        if not action:
            return None

        result = await action.async_call()
        total_bytes_received: Optional[int] = result.get("NewTotalBytesReceived")
        return total_bytes_received

    async def async_get_total_bytes_sent(self) -> Optional[int]:
        """Get total bytes sent."""
        action = self._action("WANCIC", "GetTotalBytesSent")
        if not action:
            return None

        result = await action.async_call()
        total_bytes_sent: Optional[int] = result.get("NewTotalBytesSent")
        return total_bytes_sent

    async def async_get_total_packets_received(self) -> Optional[int]:
        """Get total packets received."""
        action = self._action("WANCIC", "GetTotalPacketsReceived")
        if not action:
            return None

        result = await action.async_call()
        total_packets_received: Optional[int] = result.get("NewTotalPacketsReceived")
        return total_packets_received

    async def async_get_total_packets_sent(self) -> Optional[int]:
        """Get total packets sent."""
        action = self._action("WANCIC", "GetTotalPacketsSent")
        if not action:
            return None

        result = await action.async_call()
        total_packets_sent: Optional[int] = result.get("NewTotalPacketsSent")
        return total_packets_sent

    async def async_get_enabled_for_internet(self) -> Optional[bool]:
        """Get internet access enabled state."""
        action = self._action("WANCIC", "GetEnabledForInternet")
        if not action:
            return None

        result = await action.async_call()
        enabled_for_internet: Optional[bool] = result.get("NewEnabledForInternet")
        return enabled_for_internet

    async def async_set_enabled_for_internet(self, enabled: bool) -> None:
        """
        Set internet access enabled state.

        :param enabled whether access should be enabled
        """
        action = self._action("WANCIC", "SetEnabledForInternet")
        if not action:
            return

        await action.async_call(NewEnabledForInternet=enabled)

    async def async_get_common_link_properties(self) -> Optional[CommonLinkProperties]:
        """Get common link properties."""
        action = self._action("WANCIC", "GetCommonLinkProperties")
        if not action:
            return None

        result = await action.async_call()
        return CommonLinkProperties(
            result["NewWANAccessType"],
            int(result["NewLayer1UpstreamMaxBitRate"]),
            int(result["NewLayer1DownstreamMaxBitRate"]),
            result["NewPhysicalLinkStatus"],
        )

    async def async_get_external_ip_address(
        self, services: Optional[Sequence[str]] = None
    ) -> Optional[str]:
        """
        Get the external IP address.

        :param services List of service names to try to get action from, defaults to [WANIPC,WANPPP]
        """
        services = services or ["WANIPC", "WANPPP"]
        action = self._any_action(services, "GetExternalIPAddress")
        if not action:
            return None

        result = await action.async_call()
        external_ip_address: Optional[str] = result.get("NewExternalIPAddress")
        return external_ip_address

    async def async_get_generic_port_mapping_entry(
        self, port_mapping_index: int, services: Optional[List[str]] = None
    ) -> Optional[PortMappingEntry]:
        """
        Get generic port mapping entry.

        :param port_mapping_index Index of port mapping entry
        :param services List of service names to try to get action from, defaults to [WANIPC,WANPPP]
        """
        services = services or ["WANIPC", "WANPPP"]
        action = self._any_action(services, "GetGenericPortMappingEntry")
        if not action:
            return None

        result = await action.async_call(NewPortMappingIndex=port_mapping_index)
        return PortMappingEntry(
            IPv4Address(result["NewRemoteHost"])
            if result.get("NewRemoteHost")
            else None,
            result["NewExternalPort"],
            result["NewProtocol"],
            result["NewInternalPort"],
            IPv4Address(result["NewInternalClient"]),
            result["NewEnabled"],
            result["NewPortMappingDescription"],
            timedelta(seconds=result["NewLeaseDuration"])
            if result.get("NewLeaseDuration")
            else None,
        )

    async def async_get_specific_port_mapping_entry(
        self,
        remote_host: Optional[IPv4Address],
        external_port: int,
        protocol: str,
        services: Optional[List[str]] = None,
    ) -> Optional[PortMappingEntry]:
        """
        Get specific port mapping entry.

        :param remote_host Address of remote host or None
        :param external_port External port
        :param protocol Protocol, 'TCP' or 'UDP'
        :param services List of service names to try to get action from, defaults to [WANIPC,WANPPP]
        """
        services = services or ["WANIPC", "WANPPP"]
        action = self._any_action(services, "GetSpecificPortMappingEntry")
        if not action:
            return None

        result = await action.async_call(
            NewRemoteHost=remote_host.exploded if remote_host else "",
            NewExternalPort=external_port,
            NewProtocol=protocol,
        )
        return PortMappingEntry(
            remote_host,
            external_port,
            protocol,
            result["NewInternalPort"],
            IPv4Address(result["NewInternalClient"]),
            result["NewEnabled"],
            result["NewPortMappingDescription"],
            timedelta(seconds=result["NewLeaseDuration"])
            if result.get("NewLeaseDuration")
            else None,
        )

    async def async_add_port_mapping(
        self,
        remote_host: IPv4Address,
        external_port: int,
        protocol: str,
        internal_port: int,
        internal_client: IPv4Address,
        enabled: bool,
        description: str,
        lease_duration: timedelta,
        services: Optional[List[str]] = None,
    ) -> None:
        """
        Add a port mapping.

        :param remote_host Address of remote host or None
        :param external_port External port
        :param protocol Protocol, 'TCP' or 'UDP'
        :param internal_port Internal port
        :param internal_client Address of internal host
        :param enabled Port mapping enabled
        :param description Description for port mapping
        :param lease_duration Lease duration
        :param services List of service names to try to get action from, defaults to [WANIPC,WANPPP]
        """
        # pylint: disable=too-many-arguments
        services = services or ["WANIPC", "WANPPP"]
        action = self._any_action(services, "AddPortMapping")
        if not action:
            return

        await action.async_call(
            NewRemoteHost=remote_host.exploded if remote_host else "",
            NewExternalPort=external_port,
            NewProtocol=protocol,
            NewInternalPort=internal_port,
            NewInternalClient=internal_client.exploded,
            NewEnabled=enabled,
            NewPortMappingDescription=description,
            NewLeaseDuration=int(lease_duration.seconds) if lease_duration else 0,
        )

    async def async_delete_port_mapping(
        self,
        remote_host: IPv4Address,
        external_port: int,
        protocol: str,
        services: Optional[List[str]] = None,
    ) -> None:
        """
        Delete an existing port mapping.

        :param remote_host Address of remote host or None
        :param external_port External port
        :param protocol Protocol, 'TCP' or 'UDP'
        :param services List of service names to try to get action from, defaults to [WANIPC,WANPPP]
        """
        services = services or ["WANIPC", "WANPPP"]
        action = self._any_action(services, "DeletePortMapping")
        if not action:
            return

        await action.async_call(
            NewRemoteHost=remote_host.exploded if remote_host else "",
            NewExternalPort=external_port,
            NewProtocol=protocol,
        )

    async def async_get_connection_type_info(
        self, services: Optional[Sequence[str]] = None
    ) -> Optional[ConnectionTypeInfo]:
        """
        Get connection type info.

        :param services List of service names to try to get action from, defaults to [WANIPC,WANPPP]
        """
        services = services or ["WANIPC", "WANPPP"]
        action = self._any_action(services, "GetConnectionTypeInfo")
        if not action:
            return None

        result = await action.async_call()
        return ConnectionTypeInfo(
            result["NewConnectionType"], result["NewPossibleConnectionTypes"]
        )

    async def async_set_connection_type(
        self, connection_type: str, services: Optional[List[str]] = None
    ) -> None:
        """
        Set connection type.

        :param connection_type connection type
        :param services List of service names to try to get action from, defaults to [WANIPC,WANPPP]
        """
        services = services or ["WANIPC", "WANPPP"]
        action = self._any_action(services, "SetConnectionType")
        if not action:
            return

        await action.async_call(NewConnectionType=connection_type)

    async def async_request_connection(
        self, services: Optional[Sequence[str]] = None
    ) -> None:
        """
        Request connection.

        :param services List of service names to try to get action from, defaults to [WANIPC,WANPPP]
        """
        services = services or ["WANIPC", "WANPPP"]
        action = self._any_action(services, "RequestConnection")
        if not action:
            return

        await action.async_call()

    async def async_request_termination(
        self, services: Optional[Sequence[str]] = None
    ) -> None:
        """
        Request connection termination.

        :param services List of service names to try to get action from, defaults to [WANIPC,WANPPP]
        """
        services = services or ["WANIPC", "WANPPP"]
        action = self._any_action(services, "RequestTermination")
        if not action:
            return

        await action.async_call()

    async def async_force_termination(
        self, services: Optional[Sequence[str]] = None
    ) -> None:
        """
        Force connection termination.

        :param services List of service names to try to get action from, defaults to [WANIPC,WANPPP]
        """
        services = services or ["WANIPC", "WANPPP"]
        action = self._any_action(services, "ForceTermination")
        if not action:
            return

        await action.async_call()

    async def async_get_status_info(
        self, services: Optional[Sequence[str]] = None
    ) -> Optional[StatusInfo]:
        """
        Get status info.

        :param services List of service names to try to get action from, defaults to [WANIPC,WANPPP]
        """
        services = services or ["WANIPC", "WANPPP"]
        action = self._any_action(services, "GetStatusInfo")
        if not action:
            return None

        try:
            result = await action.async_call()
        except ValueError:
            _LOGGER.debug("Caught ValueError parsing results")
            return None

        return StatusInfo(
            result["NewConnectionStatus"],
            result["NewLastConnectionError"],
            result["NewUptime"],
        )

    async def async_get_port_mapping_number_of_entries(
        self, services: Optional[Sequence[str]] = None
    ) -> Optional[int]:
        """
        Get number of port mapping entries.

        :param services List of service names to try to get action from, defaults to [WANIPC,WANPPP]
        """
        services = services or ["WANIPC", "WANPPP"]
        action = self._any_action(services, "GetPortMappingNumberOfEntries")
        if not action:
            return None

        result = await action.async_call()
        number_of_entries: Optional[str] = result.get(
            "NewPortMappingNumberOfEntries"
        )  # str?
        if number_of_entries is None:
            return None
        return int(number_of_entries)

    async def async_get_nat_rsip_status(
        self, services: Optional[Sequence[str]] = None
    ) -> Optional[NatRsipStatusInfo]:
        """
        Get NAT enabled and RSIP availability statuses.

        :param services List of service names to try to get action from, defaults to [WANIPC,WANPPP]
        """
        services = services or ["WANIPC", "WANPPP"]
        action = self._any_action(services, "GetNATRSIPStatus")
        if not action:
            return None

        result = await action.async_call()
        return NatRsipStatusInfo(result["NewNATEnabled"], result["NewRSIPAvailable"])

    async def async_get_default_connection_service(self) -> Optional[str]:
        """Get default connection service."""
        action = self._action("L3FWD", "GetDefaultConnectionService")
        if not action:
            return None

        result = await action.async_call()
        default_connection_service: Optional[str] = result.get(
            "NewDefaultConnectionService"
        )
        return default_connection_service

    async def async_set_default_connection_service(self, service: str) -> None:
        """
        Set default connection service.

        :param service default connection service
        """
        action = self._action("L3FWD", "SetDefaultConnectionService")
        if not action:
            return

        await action.async_call(NewDefaultConnectionService=service)

    async def async_get_traffic_and_status_data(
        self,
    ) -> IgdState:
        """
        Get all traffic data at once, including derived data.

        Data:
        * total bytes received
        * total bytes sent
        * total packets received
        * total packets sent
        * bytes per second received (derived from last update)
        * bytes per second sent (derived from last update)
        * packets per second received (derived from last update)
        * packets per second sent (derived from last update)
        """
        timestamp = datetime.now()
        values = await asyncio.gather(
            self.async_get_total_bytes_received(),
            self.async_get_total_bytes_sent(),
            self.async_get_total_packets_received(),
            self.async_get_total_packets_sent(),
            self.async_get_status_info(),
            self.async_get_external_ip_address(),
            return_exceptions=True,
        )

        kibibytes_per_sec_received = _derive_value_per_second(
            BYTES_RECEIVED,
            timestamp,
            values[0],
            self._last_traffic_state.timestamp,
            self._last_traffic_state.bytes_received,
        )
        kibibytes_per_sec_sent = _derive_value_per_second(
            BYTES_SENT,
            timestamp,
            values[1],
            self._last_traffic_state.timestamp,
            self._last_traffic_state.bytes_sent,
        )
        packets_per_sec_received = _derive_value_per_second(
            PACKETS_RECEIVED,
            timestamp,
            values[2],
            self._last_traffic_state.timestamp,
            self._last_traffic_state.packets_received,
        )
        packets_per_sec_sent = _derive_value_per_second(
            PACKETS_SENT,
            timestamp,
            values[3],
            self._last_traffic_state.timestamp,
            self._last_traffic_state.packets_sent,
        )

        self._last_traffic_state = TrafficCounterState(
            timestamp=timestamp,
            bytes_received=values[0],
            bytes_sent=values[1],
            packets_received=values[2],
            packets_sent=values[3],
        )

        non_exceptions = [value for value in values if not isinstance(value, Exception)]
        if not non_exceptions:
            # Raise any exception to indicate something was very wrong.
            raise values[0]

        return IgdState(
            timestamp=timestamp,
            bytes_received=values[0],
            bytes_sent=values[1],
            packets_received=values[2],
            packets_sent=values[3],
            kibibytes_per_sec_received=kibibytes_per_sec_received,
            kibibytes_per_sec_sent=kibibytes_per_sec_sent,
            packets_per_sec_received=packets_per_sec_received,
            packets_per_sec_sent=packets_per_sec_sent,
            status_info=values[4],
            external_ip_address=values[5],
        )
