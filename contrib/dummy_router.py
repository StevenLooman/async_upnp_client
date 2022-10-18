#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Dummy router supporting IGD."""
# Instructions:
# - Change `SOURCE``. When using IPv6, be sure to set the scope_id, the last value in the tuple.
# - Run this module.
# - Run upnp-client (change IP to your own IP):
#    upnp-client call-action 'http://0.0.0.0:8000/device.xml' \
#                WANCIC/GetTotalPacketsReceived

import asyncio
import logging
import xml.etree.ElementTree as ET
from time import time
from typing import Dict, Mapping, Sequence, Type

from async_upnp_client.client import UpnpRequester, UpnpStateVariable
from async_upnp_client.const import (
    STATE_VARIABLE_TYPE_MAPPING,
    DeviceInfo,
    ServiceInfo,
    StateVariableTypeInfo,
)

from async_upnp_client.server import UpnpServer, UpnpServerDevice, UpnpServerService, callable_action

logging.basicConfig(level=logging.DEBUG)
LOGGER = logging.getLogger("dummy_router")
LOGGER_SSDP_TRAFFIC = logging.getLogger("async_upnp_client.traffic")
LOGGER_SSDP_TRAFFIC.setLevel(logging.WARNING)
SOURCE = ("172.24.83.184", 0)  # Your IP here!
# SOURCE = ("fe80::215:5dff:fe3e:6d23", 0, 0, 6)  # Your IP here!
HTTP_PORT = 8000


class WANIPConnectionService(UpnpServerService):
    """WANIPConnection service."""

    SERVICE_DEFINITION = ServiceInfo(
        service_id="urn:upnp-org:serviceId:WANIPConnection1",
        service_type="urn:schemas-upnp-org:service:WANIPConnection:1",
        control_url="/upnp/control/WANIPConnection1",
        event_sub_url="/upnp/event/WANIPConnection1",
        scpd_url="/WANIPConnection_1.xml",
        xml=ET.Element("server_service"),
    )

    STATE_VARIABLE_DEFINITIONS = {
        "ExternalIPAddress": StateVariableTypeInfo(
            data_type="string",
            data_type_mapping=STATE_VARIABLE_TYPE_MAPPING["string"],
            default_value="1.2.3.4",
            allowed_value_range={},
            allowed_values=None,
            xml=ET.Element("server_stateVariable"),
        ),
        "ConnectionStatus": StateVariableTypeInfo(
            data_type="string",
            data_type_mapping=STATE_VARIABLE_TYPE_MAPPING["string"],
            default_value="Unconfigured",
            allowed_value_range={},
            allowed_values=[
                "Unconfigured",
                "Authenticating",
                "Connecting",
                "Connected",
                "PendingDisconnect",
                "Disconnecting",
                "Disconnected",
            ],
            xml=ET.Element("server_stateVariable"),
        ),
        "LastConnectionError": StateVariableTypeInfo(
            data_type="string",
            data_type_mapping=STATE_VARIABLE_TYPE_MAPPING["string"],
            default_value="ERROR_NONE",
            allowed_value_range={},
            allowed_values=[
                "ERROR_NONE",
            ],
            xml=ET.Element("server_stateVariable"),
        ),
        "Uptime": StateVariableTypeInfo(
            data_type="ui4",
            data_type_mapping=STATE_VARIABLE_TYPE_MAPPING["ui4"],
            default_value="0",
            allowed_value_range={},
            allowed_values=None,
            xml=ET.Element("server_stateVariable"),
        ),
    }

    @callable_action(
        name="GetStatusInfo",
        in_args={},
        out_args={
            "NewConnectionStatus": "ConnectionStatus",
            "NewLastConnectionError": "LastConnectionError",
            "NewUptime": "Uptime",
        },
    )
    async def get_status_info(self) -> Dict[str, UpnpStateVariable]:
        """Get status info."""
        # from async_upnp_client.exceptions import UpnpActionError, UpnpActionErrorCode
        # raise UpnpActionError(
        #     error_code=UpnpActionErrorCode.INVALID_ACTION, error_desc="Invalid action"
        # )
        return {
            "NewConnectionStatus": self.state_variable("ConnectionStatus"),
            "NewLastConnectionError": self.state_variable("LastConnectionError"),
            "NewUptime": self.state_variable("Uptime"),
        }

    @callable_action(
        name="GetExternalIPAddress",
        in_args={},
        out_args={
            "NewExternalIPAddress": "ExternalIPAddress",
        },
    )
    async def get_external_ip_address(self) -> Dict[str, UpnpStateVariable]:
        """Get external IP address."""
        # from async_upnp_client.exceptions import UpnpActionError, UpnpActionErrorCode
        # raise UpnpActionError(
        #     error_code=UpnpActionErrorCode.INVALID_ACTION, error_desc="Invalid action"
        # )
        return {
            "NewExternalIPAddress": self.state_variable("ExternalIPAddress"),
        }


class WanConnectionDevice(UpnpServerDevice):
    """WAN Connection device."""

    DEVICE_DEFINITION = DeviceInfo(
        device_type="urn:schemas-upnp-org:device:WANConnectionDevice:1",
        friendly_name="Dummy Router WAN Connection Device",
        manufacturer="Steven",
        manufacturer_url=None,
        model_name="DummyRouter v1",
        model_url=None,
        udn="uuid:51e00c19-c8f3-4b28-9ef1-7f562f204c82",
        upc=None,
        model_description="Dummy Router IGD",
        model_number="v0.0.1",
        serial_number="0000001",
        presentation_url=None,
        url="/device.xml",
        icons=[],
        xml=ET.Element("server_device"),
    )
    EMBEDDED_DEVICES: Sequence[Type[UpnpServerDevice]] = []
    SERVICES = [WANIPConnectionService]

    def __init__(self, requester: UpnpRequester, base_uri: str, boot_id: int, config_id: int) -> None:
        """Initialize."""
        super().__init__(
            requester=requester,
            base_uri=base_uri,
            boot_id=boot_id,
            config_id=config_id,
        )


class WANCommonInterfaceConfigService(UpnpServerService):
    """WANCommonInterfaceConfig service."""

    SERVICE_DEFINITION = ServiceInfo(
        service_id="urn:upnp-org:serviceId:WANCommonInterfaceConfig1",
        service_type="urn:schemas-upnp-org:service:WANCommonInterfaceConfig:1",
        control_url="/upnp/control/WANCommonInterfaceConfig1",
        event_sub_url="/upnp/event/WANCommonInterfaceConfig1",
        scpd_url="/WANCommonInterfaceConfig_1.xml",
        xml=ET.Element("server_service"),
    )

    STATE_VARIABLE_DEFINITIONS = {
        "TotalBytesReceived": StateVariableTypeInfo(
            data_type="ui4",
            data_type_mapping=STATE_VARIABLE_TYPE_MAPPING["ui4"],
            default_value="0",
            allowed_value_range={},
            allowed_values=None,
            xml=ET.Element("server_stateVariable"),
        ),
        "TotalBytesSent": StateVariableTypeInfo(
            data_type="ui4",
            data_type_mapping=STATE_VARIABLE_TYPE_MAPPING["ui4"],
            default_value="0",
            allowed_value_range={},
            allowed_values=None,
            xml=ET.Element("server_stateVariable"),
        ),
        "TotalPacketsReceived": StateVariableTypeInfo(
            data_type="ui4",
            data_type_mapping=STATE_VARIABLE_TYPE_MAPPING["ui4"],
            default_value="0",
            allowed_value_range={},
            allowed_values=None,
            xml=ET.Element("server_stateVariable"),
        ),
        "TotalPacketsSent": StateVariableTypeInfo(
            data_type="ui4",
            data_type_mapping=STATE_VARIABLE_TYPE_MAPPING["ui4"],
            default_value="0",
            allowed_value_range={},
            allowed_values=None,
            xml=ET.Element("server_stateVariable"),
        ),
    }

    MAX_COUNTER = 2**32

    def _update_bytes(self, state_var_name: str) -> None:
        """Update bytes state variable."""
        new_bytes = int(time() * 1000) % self.MAX_COUNTER
        self.state_variable(state_var_name).value = new_bytes

    def _update_packets(self, state_var_name: str) -> None:
        """Update state variable values."""
        new_packets = int(time()) % self.MAX_COUNTER
        self.state_variable(state_var_name).value = new_packets
        self.state_variable(state_var_name).value = new_packets

    @callable_action(
        name="GetTotalBytesReceived",
        in_args={},
        out_args={
            "NewTotalBytesReceived": "TotalBytesReceived",
        },
    )
    async def get_total_bytes_received(self) -> Dict[str, UpnpStateVariable]:
        """Get total bytes received."""
        self._update_bytes("TotalBytesReceived")
        return {
            "NewTotalBytesReceived": self.state_variable("TotalBytesReceived"),
        }

    @callable_action(
        name="GetTotalBytesSent",
        in_args={},
        out_args={
            "NewTotalBytesSent": "TotalBytesSent",
        },
    )
    async def get_total_bytes_sent(self) -> Dict[str, UpnpStateVariable]:
        """Get total bytes sent."""
        self._update_bytes("TotalBytesSent")
        return {
            "NewTotalBytesSent": self.state_variable("TotalBytesSent"),
        }

    @callable_action(
        name="GetTotalPacketsReceived",
        in_args={},
        out_args={
            "NewTotalPacketsReceived": "TotalPacketsReceived",
        },
    )
    async def get_total_packets_received(self) -> Dict[str, UpnpStateVariable]:
        """Get total packets received."""
        self._update_packets("TotalPacketsReceived")
        return {
            "NewTotalPacketsReceived": self.state_variable("TotalPacketsReceived"),
        }

    @callable_action(
        name="GetTotalPacketsSent",
        in_args={},
        out_args={
            "NewTotalPacketsSent": "TotalPacketsSent",
        },
    )
    async def get_total_packets_sent(self) -> Dict[str, UpnpStateVariable]:
        """Get total packets sent."""
        self._update_packets("TotalPacketsSent")
        return {
            "NewTotalPacketsSent": self.state_variable("TotalPacketsSent"),
        }


class WanDevice(UpnpServerDevice):
    """WAN device."""

    DEVICE_DEFINITION = DeviceInfo(
        device_type="urn:schemas-upnp-org:device:WANDevice:1",
        friendly_name="Dummy Router WAN Device",
        manufacturer="Steven",
        manufacturer_url=None,
        model_name="DummyRouter v1",
        model_url=None,
        udn="uuid:51e00c19-c8f3-4b28-9ef1-7f562f204c81",
        upc=None,
        model_description="Dummy Router IGD",
        model_number="v0.0.1",
        serial_number="0000001",
        presentation_url=None,
        url="/device.xml",
        icons=[],
        xml=ET.Element("server_device"),
    )
    EMBEDDED_DEVICES = [WanConnectionDevice]
    SERVICES = [WANCommonInterfaceConfigService]

    def __init__(self, requester: UpnpRequester, base_uri: str, boot_id: int, config_id: int) -> None:
        """Initialize."""
        super().__init__(
            requester=requester,
            base_uri=base_uri,
            boot_id=boot_id,
            config_id=config_id,
        )


class Layer3ForwardingService(UpnpServerService):
    """Layer3Forwarding service."""

    SERVICE_DEFINITION = ServiceInfo(
        service_id="urn:upnp-org:serviceId:Layer3Forwarding1",
        service_type="urn:schemas-upnp-org:service:Layer3Forwarding:1",
        control_url="/upnp/control/Layer3Forwarding1",
        event_sub_url="/upnp/event/Layer3Forwarding1",
        scpd_url="/Layer3Forwarding_1.xml",
        xml=ET.Element("server_service"),
    )

    STATE_VARIABLE_DEFINITIONS: Mapping[str, StateVariableTypeInfo] = {}


class IgdDevice(UpnpServerDevice):
    """IGD device."""

    DEVICE_DEFINITION = DeviceInfo(
        device_type="urn:schemas-upnp-org:device:InternetGatewayDevice:1",
        friendly_name="Dummy Router",
        manufacturer="Steven",
        manufacturer_url=None,
        model_name="DummyRouter v1",
        model_url=None,
        udn="uuid:51e00c19-c8f3-4b28-9ef1-7f562f204c80",
        upc=None,
        model_description="Dummy Router IGD",
        model_number="v0.0.1",
        serial_number="0000001",
        presentation_url=None,
        url="/device.xml",
        icons=[],
        xml=ET.Element("server_device"),
    )
    EMBEDDED_DEVICES = [WanDevice]
    SERVICES = [Layer3ForwardingService]

    def __init__(self, requester: UpnpRequester, base_uri: str, boot_id: int, config_id: int) -> None:
        """Initialize."""
        super().__init__(
            requester=requester,
            base_uri=base_uri,
            boot_id=boot_id,
            config_id=config_id,
        )


async def async_main() -> None:
    """Main."""
    boot_id = int(time())
    config_id = 1
    server = UpnpServer(IgdDevice, SOURCE, http_port=HTTP_PORT, boot_id=boot_id, config_id=config_id)
    await server.async_start()

    try:
        while True:
            await asyncio.sleep(3600)
    except KeyboardInterrupt:
        pass

    await server.async_stop()


if __name__ == "__main__":
    asyncio.run(async_main())
