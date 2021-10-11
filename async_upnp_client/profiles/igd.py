# -*- coding: utf-8 -*-
"""UPnP IGD module."""

import logging
from datetime import timedelta
from ipaddress import IPv4Address
from typing import List, NamedTuple, Optional, Sequence

from async_upnp_client import UpnpAction
from async_upnp_client.profiles.profile import UpnpProfileDevice

_LOGGER = logging.getLogger(__name__)


CommonLinkProperties = NamedTuple(
    "CommonLinkProperties",
    [
        ("wan_access_type", str),
        ("layer1_upstream_max_bit_rate", int),
        ("layer1_downstream_max_bit_rate", int),
        ("physical_link_status", str),
    ],
)

ConnectionTypeInfo = NamedTuple(
    "ConnectionTypeInfo", [("connection_type", str), ("possible_connection_types", str)]
)

StatusInfo = NamedTuple(
    "StatusInfo",
    [("connection_status", str), ("last_connection_error", str), ("uptime", int)],
)

NatRsipStatusInfo = NamedTuple(
    "NatRsipStatusInfo", [("nat_enabled", bool), ("rsip_available", bool)]
)

PortMappingEntry = NamedTuple(
    "PortMappingEntry",
    [
        ("remote_host", Optional[IPv4Address]),
        ("external_port", int),
        ("protocol", str),
        ("internal_port", int),
        ("internal_client", IPv4Address),
        ("enabled", bool),
        ("description", str),
        ("lease_duration", Optional[timedelta]),
    ],
)


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
