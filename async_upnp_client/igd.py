# -*- coding: utf-8 -*-
"""UPnP IGD module."""

from datetime import timedelta
from ipaddress import IPv4Address
import logging

from async_upnp_client.profile import UpnpProfileDevice


_LOGGER = logging.getLogger(__name__)


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
