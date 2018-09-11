# -*- coding: utf-8 -*-
"""UPnP IGD module."""

from datetime import timedelta
from ipaddress import IPv4Address
import logging
from typing import NamedTuple

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


class IgdDevice(UpnpProfileDevice):
    """Representation of a IGD device."""

    _SERVICE_TYPES = {
        'WANPPPC': {
            'urn:schemas-upnp-org:service:WANPPPConnection:1',
        },
        'WANIPC': {
            'urn:schemas-upnp-org:service:WANIPConnection:1',
        },
        'WANCIC': {
            'urn:schemas-upnp-org:service:WANCommonInterfaceConfig:1',
        }
    }

    async def async_get_total_bytes_received(self):
        """Get total bytes received."""
        action = self._action('WANCIC', 'GetTotalBytesReceived')
        result = await action.async_call()
        return result['NewTotalBytesReceived']

    async def async_get_total_bytes_sent(self):
        """Get total bytes sent."""
        action = self._action('WANCIC', 'GetTotalBytesSent')
        result = await action.async_call()
        return result['NewTotalBytesSent']

    async def async_get_total_packets_received(self):
        """Get total packets received."""
        # pylint: disable=invalid-name
        action = self._action('WANCIC', 'GetTotalPacketsReceived')
        result = await action.async_call()
        return result['NewTotalPacketsReceived']

    async def async_get_total_packets_sent(self):
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
        action = self._action('WANCIC', 'GetCommonLinkProperties')
        result = await action.async_call()
        return CommonLinkProperties(
            result['NewWANAccessType'],
            result['NewLayer1UpstreamMaxBitRate'],
            result['NewLayer1DownstreamMaxBitRate'],
            result['NewPhysicalLinkStatus'])

    async def async_get_external_ip_address(self):
        """Get the external IP address."""
        action = self._action('WANIPC', 'GetExternalIPAddress')
        result = await action.async_call()
        return result['NewExternalIPAddress']

    async def async_add_port_mapping(self,
                                     remote_host: IPv4Address,
                                     external_port: int,
                                     protocol: str,
                                     internal_port: int,
                                     internal_client: IPv4Address,
                                     enabled: bool,
                                     description: str,
                                     lease_duration: timedelta):
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
        """
        # pylint: disable=too-many-arguments
        action = self._action('WANIPC', 'AddPortMapping')
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
                                        protocol: str):
        """
        Delete an existing port mapping.

        :param remote_host Address of remote host or None
        :param external_port External port
        :param protocol Protocol, 'TCP' or 'UDP'
        """
        action = self._action('WANIPC', 'DeletePortMapping')
        await action.async_call(
            NewRemoteHost=remote_host.exploded if remote_host else '',
            NewExternalPort=external_port,
            NewProtocol=protocol)

    async def async_get_connection_type_info(self) -> ConnectionTypeInfo:
        """Get connection type info."""
        action = self._action('WANIPC', 'GetConnectionTypeInfo')
        result = await action.async_call()
        return ConnectionTypeInfo(
            result['NewConnectionType'],
            result['NewPossibleConnectionTypes'])

    async def async_get_status_info(self) -> StatusInfo:
        """Get status info."""
        action = self._action('WANIPC', 'GetStatusInfo')
        result = await action.async_call()
        return StatusInfo(
            result['NewConnectionStatus'],
            result['NewLastConnectionError'],
            result['NewUptime'])
