# -*- coding: utf-8 -*-
"""UPnP IGD module."""

from datetime import timedelta
from ipaddress import IPv4Address
import logging
from typing import List, NamedTuple, Optional

from async_upnp_client.profile import UpnpProfileDevice


_LOGGER = logging.getLogger(__name__)


CommonLinkProperties = NamedTuple(
    'CommonLinkProperties', [
        ('wan_access_type', str),
        ('layer1_upstream_max_bit_rate', int),
        ('layer1_downstream_max_bit_rate', int),
        ('physical_link_status', str)])

ConnectionTypeInfo = NamedTuple(
    'ConnectionTypeInfo', [
        ('connection_type', str),
        ('possible_connection_types', str)])

StatusInfo = NamedTuple(
    'StatusInfo', [
        ('connection_status', str),
        ('last_connection_error', str),
        ('uptime', int)])

NatRsipStatusInfo = NamedTuple(
    'NatRsipStatusInfo', [
        ('nat_enabled', bool),
        ('rsip_available', bool)])

PortMappingEntry = NamedTuple(
    'PortMappingEntry', [
        ('remote_host', Optional[IPv4Address]),
        ('external_port', int),
        ('protocol', str),
        ('internal_port', int),
        ('internal_client', IPv4Address),
        ('enabled', bool),
        ('description', str),
        ('lease_duration', Optional[timedelta])])


class IgdDevice(UpnpProfileDevice):
    """Representation of a IGD device."""

    # pylint: disable=too-many-public-methods

    DEVICE_TYPES = [
        'urn:schemas-upnp-org:device:InternetGatewayDevice:1',
        'urn:schemas-upnp-org:device:InternetGatewayDevice:2',
    ]

    _SERVICE_TYPES = {
        'WANPPPC': {
            'urn:schemas-upnp-org:service:WANPPPConnection:1',
        },
        'WANIPC': {
            'urn:schemas-upnp-org:service:WANIPConnection:1',
        },
        'WANCIC': {
            'urn:schemas-upnp-org:service:WANCommonInterfaceConfig:1',
        },
        'L3FWD': {
            'urn:schemas-upnp-org:service:Layer3Forwarding:1',
        },
    }

    def _any_action(self, service_names: List[str], action_name: str):
        for service_name in service_names:
            action = self._action(service_name, action_name)
            if action is not None:
                return action
        return None

    async def async_get_total_bytes_received(self) -> int:
        """Get total bytes received."""
        action = self._action('WANCIC', 'GetTotalBytesReceived')
        result = await action.async_call()
        return result['NewTotalBytesReceived']

    async def async_get_total_bytes_sent(self) -> int:
        """Get total bytes sent."""
        action = self._action('WANCIC', 'GetTotalBytesSent')
        result = await action.async_call()
        return result['NewTotalBytesSent']

    async def async_get_total_packets_received(self) -> int:
        """Get total packets received."""
        # pylint: disable=invalid-name
        action = self._action('WANCIC', 'GetTotalPacketsReceived')
        result = await action.async_call()
        return result['NewTotalPacketsReceived']

    async def async_get_total_packets_sent(self) -> int:
        """Get total packets sent."""
        action = self._action('WANCIC', 'GetTotalPacketsSent')
        result = await action.async_call()
        return result['NewTotalPacketsSent']

    async def async_get_enabled_for_internet(self) -> bool:
        """Get internet access enabled state."""
        action = self._action('WANCIC', 'GetEnabledForInternet')
        result = await action.async_call()
        return result['NewEnabledForInternet']

    async def async_set_enabled_for_internet(self, enabled: bool) -> None:
        """
        Set internet access enabled state.

        :param enabled whether access should be enabled
        """
        action = self._action('WANCIC', 'SetEnabledForInternet')
        await action.async_call(NewEnabledForInternet=enabled)

    async def async_get_common_link_properties(self) -> CommonLinkProperties:
        """Get common link properties."""
        # pylint: disable=invalid-name
        action = self._action('WANCIC', 'GetCommonLinkProperties')
        result = await action.async_call()
        return CommonLinkProperties(
            result['NewWANAccessType'],
            result['NewLayer1UpstreamMaxBitRate'],
            result['NewLayer1DownstreamMaxBitRate'],
            result['NewPhysicalLinkStatus'])

    async def async_get_external_ip_address(self, services: List = None) -> str:
        """
        Get the external IP address.

        :param services List of service names to try to get action from, defaults to [WANIPC,WANPPP]
        """
        services = services or ['WANIPC', 'WANPPP']
        action = self._any_action(services, 'GetExternalIPAddress')
        result = await action.async_call()
        return result['NewExternalIPAddress']

    async def async_get_generic_port_mapping_entry(self,
                                                   port_mapping_index: int,
                                                   services: List = None) -> PortMappingEntry:
        """
        Get generic port mapping entry.

        :param port_mapping_index Index of port mapping entry
        :param services List of service names to try to get action from, defaults to [WANIPC,WANPPP]
        """
        # pylint: disable=invalid-name
        services = services or ['WANIPC', 'WANPPP']
        action = self._any_action(services, 'GetGenericPortMappingEntry')
        result = await action.async_call(
            NewPortMappingIndex=port_mapping_index)
        return PortMappingEntry(
            IPv4Address(result['NewRemoteHost']) if result['NewRemoteHost'] else None,
            result['NewExternalPort'],
            result['NewProtocol'],
            result['NewInternalPort'],
            IPv4Address(result['NewInternalClient']),
            result['NewEnabled'],
            result['NewPortMappingDescription'],
            timedelta(seconds=result['NewLeaseDuration']) if result['NewLeaseDuration'] else None)

    async def async_get_specific_port_mapping_entry(self,
                                                    remote_host: Optional[IPv4Address],
                                                    external_port: int,
                                                    protocol: str,
                                                    services: List = None) -> PortMappingEntry:
        """
        Get specific port mapping entry.

        :param remote_host Address of remote host or None
        :param external_port External port
        :param protocol Protocol, 'TCP' or 'UDP'
        :param services List of service names to try to get action from, defaults to [WANIPC,WANPPP]
        """
        # pylint: disable=invalid-name
        services = services or ['WANIPC', 'WANPPP']
        action = self._any_action(services, 'GetSpecificPortMappingEntry')
        result = await action.async_call(
            NewRemoteHost=remote_host.exploded if remote_host else '',
            NewExternalPort=external_port,
            NewProtocol=protocol)
        return PortMappingEntry(
            remote_host,
            external_port,
            protocol,
            result['NewInternalPort'],
            IPv4Address(result['NewInternalClient']),
            result['NewEnabled'],
            result['NewPortMappingDescription'],
            timedelta(seconds=result['NewLeaseDuration']) if result['NewLeaseDuration'] else None)

    async def async_add_port_mapping(self,
                                     remote_host: IPv4Address,
                                     external_port: int,
                                     protocol: str,
                                     internal_port: int,
                                     internal_client: IPv4Address,
                                     enabled: bool,
                                     description: str,
                                     lease_duration: timedelta,
                                     services: List = None):
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
        services = services or ['WANIPC', 'WANPPP']
        action = self._any_action(services, 'AddPortMapping')
        await action.async_call(
            NewRemoteHost=remote_host.exploded if remote_host else '',
            NewExternalPort=external_port,
            NewProtocol=protocol,
            NewInternalPort=internal_port,
            NewInternalClient=internal_client.exploded,
            NewEnabled=enabled,
            NewPortMappingDescription=description,
            NewLeaseDuration=int(lease_duration.seconds) if lease_duration else 0)

    async def async_delete_port_mapping(self,
                                        remote_host: IPv4Address,
                                        external_port: int,
                                        protocol: str,
                                        services: List = None):
        """
        Delete an existing port mapping.

        :param remote_host Address of remote host or None
        :param external_port External port
        :param protocol Protocol, 'TCP' or 'UDP'
        :param services List of service names to try to get action from, defaults to [WANIPC,WANPPP]
        """
        services = services or ['WANIPC', 'WANPPP']
        action = self._any_action(services, 'DeletePortMapping')
        await action.async_call(
            NewRemoteHost=remote_host.exploded if remote_host else '',
            NewExternalPort=external_port,
            NewProtocol=protocol)

    async def async_get_connection_type_info(self, services: List = None) -> ConnectionTypeInfo:
        """
        Get connection type info.

        :param services List of service names to try to get action from, defaults to [WANIPC,WANPPP]
        """
        services = services or ['WANIPC', 'WANPPP']
        action = self._any_action(services, 'GetConnectionTypeInfo')
        result = await action.async_call()
        return ConnectionTypeInfo(
            result['NewConnectionType'],
            result['NewPossibleConnectionTypes'])

    async def async_set_connection_type(self, connection_type: str, services: List = None) -> None:
        """
        Set connection type.

        :param connection_type connection type
        :param services List of service names to try to get action from, defaults to [WANIPC,WANPPP]
        """
        services = services or ['WANIPC', 'WANPPP']
        action = self._any_action(services, 'SetConnectionType')
        await action.async_call(NewConnectionType=connection_type)

    async def async_request_connection(self, services: List = None) -> None:
        """
        Request connection.

        :param services List of service names to try to get action from, defaults to [WANIPC,WANPPP]
        """
        services = services or ['WANIPC', 'WANPPP']
        action = self._any_action(services, 'RequestConnection')
        await action.async_call()

    async def async_request_termination(self, services: List = None) -> None:
        """
        Request connection termination.

        :param services List of service names to try to get action from, defaults to [WANIPC,WANPPP]
        """
        services = services or ['WANIPC', 'WANPPP']
        action = self._any_action(services, 'RequestTermination')
        await action.async_call()

    async def async_force_termination(self, services: List = None) -> None:
        """
        Force connection termination.

        :param services List of service names to try to get action from, defaults to [WANIPC,WANPPP]
        """
        services = services or ['WANIPC', 'WANPPP']
        action = self._action(services, 'ForceTermination')
        await action.async_call()

    async def async_get_status_info(self, services: List = None) -> StatusInfo:
        """
        Get status info.

        :param services List of service names to try to get action from, defaults to [WANIPC,WANPPP]
        """
        services = services or ['WANIPC', 'WANPPP']
        action = self._any_action(services, 'GetStatusInfo')
        result = await action.async_call()
        return StatusInfo(
            result['NewConnectionStatus'],
            result['NewLastConnectionError'],
            result['NewUptime'])

    async def async_get_port_mapping_number_of_entries(self, services: List = None) -> int:
        """
        Get number of port mapping entries.

        :param services List of service names to try to get action from, defaults to [WANIPC,WANPPP]
        """
        # pylint: disable=invalid-name
        services = services or ['WANIPC', 'WANPPP']
        action = self._any_action(services, 'GetPortMappingNumberOfEntries')
        result = await action.async_call()
        return result['NewPortMappingNumberOfEntries']

    async def async_get_nat_rsip_status(self, services: List = None) -> NatRsipStatusInfo:
        """
        Get NAT enabled and RSIP availability statuses.

        :param services List of service names to try to get action from, defaults to [WANIPC,WANPPP]
        """
        services = services or ['WANIPC', 'WANPPP']
        action = self._any_action(services, 'GetNATRSIPStatus')
        result = await action.async_call()
        return NatRsipStatusInfo(
            result['NewNATEnabled'],
            result['NewRSIPAvailable'])

    async def async_get_default_connection_service(self) -> str:
        """Get default connection service."""
        # pylint: disable=invalid-name
        action = self._action('L3FWD', 'GetDefaultConnectionService')
        result = await action.async_call()
        return result['NewDefaultConnectionService']

    async def async_set_default_connection_service(self, service: str) -> None:
        """
        Set default connection service.

        :param service default connection service
        """
        # pylint: disable=invalid-name
        action = self._action('L3FWD', 'SetDefaultConnectionService')
        await action.async_call(NewDefaultConnectionService=service)
