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
import time
import xml.etree.ElementTree as ET
from typing import Dict

from async_upnp_client.client import UpnpRequester, UpnpStateVariable
from async_upnp_client.const import (
    STATE_VARIABLE_TYPE_MAPPING,
    DeviceInfo,
    ServiceInfo,
    StateVariableTypeInfo,
)

from .server import (
    UpnpServerDevice,
    UpnpServerService,
    callable_action,
    run_server,
)

logging.basicConfig(level=logging.DEBUG)
LOGGER = logging.getLogger("dummy_router")
LOGGER_SSDP_TRAFFIC = logging.getLogger("async_upnp_client.traffic")
LOGGER_SSDP_TRAFFIC.setLevel(logging.WARNING)
SOURCE = ("0.0.0.0", 0)  # Your IP here!
HTTP_PORT = 8000


class IgdDevice(UpnpServerDevice):
    """IGD device."""

    DEVICE_DEFINITION = DeviceInfo(
        device_type="urn:schemas-upnp-org:device:InternetGatewayDevice:1",
        friendly_name="Dummy Router",
        manufacturer="Steven",
        model_name="DummyRouter v1",
        udn="uuid:51e00c19-c8f3-4b28-9ef1-7f562f204c80",
        model_description="Dummy Router IGD",
        model_number="v0.0.1",
        serial_number="0000001",
        url="/device.xml",
        icons=[],
        xml=ET.Element("server_device"),
    )

    def __init__(self, requester: UpnpRequester, base_uri: str) -> None:
        """Initialize."""
        services = [
            Layer3ForwardingService(requester=requester),
        ]
        embedded_devices = [
            WanDevice(requester=requester, base_uri=base_uri),
        ]
        super().__init__(
            requester=requester,
            base_uri=base_uri,
            services=services,
            embedded_devices=embedded_devices,
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

    STATE_VARIABLE_DEFINITIONS = {
    }


class WanDevice(UpnpServerDevice):
    """WAN device."""

    DEVICE_DEFINITION = DeviceInfo(
        device_type="urn:schemas-upnp-org:device:WANDevice:1",
        friendly_name="Dummy Router WAN Device",
        manufacturer="Steven",
        model_name="DummyRouter v1",
        udn="uuid:51e00c19-c8f3-4b28-9ef1-7f562f204c81",
        model_description="Dummy Router IGD",
        model_number="v0.0.1",
        serial_number="0000001",
        url="/device.xml",
        icons=[],
        xml=ET.Element("server_device"),
    )

    def __init__(self, requester: UpnpRequester, base_uri: str) -> None:
        """Initialize."""
        services = [
            WANCommonInterfaceConfigService(requester=requester),
        ]
        embedded_devices = [
            WanConnectionDevice(requester=requester, base_uri=base_uri)
        ]
        super().__init__(
            requester=requester,
            base_uri=base_uri,
            services=services,
            embedded_devices=embedded_devices,
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

    MAX_COUNTER = 2 ** 32

    def _update_bytes(self, state_var_name: str) -> None:
        """Update bytes state variable."""
        new_bytes = int(time.time() * 1000) % self.MAX_COUNTER
        self.state_variable(state_var_name).value = new_bytes

    def _update_packets(self, state_var_name: str) -> None:
        """Update state variable values."""
        new_packets = int(time.time()) % self.MAX_COUNTER
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


class WanConnectionDevice(UpnpServerDevice):
    """WAN Connection device."""

    DEVICE_DEFINITION = DeviceInfo(
        device_type="urn:schemas-upnp-org:device:WANConnectionDevice:1",
        friendly_name="Dummy Router WAN Connection Device",
        manufacturer="Steven",
        model_name="DummyRouter v1",
        udn="uuid:51e00c19-c8f3-4b28-9ef1-7f562f204c82",
        model_description="Dummy Router IGD",
        model_number="v0.0.1",
        serial_number="0000001",
        url="/device.xml",
        icons=[],
        xml=ET.Element("server_device"),
    )

    def __init__(self, requester: UpnpRequester, base_uri: str) -> None:
        """Initialize."""
        services = [
            WANIPConnectionService(requester=requester),
        ]
        super().__init__(
            requester=requester,
            base_uri=base_uri,
            services=services,
            embedded_devices=[],
        )


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
    }


async def async_main() -> None:
    """Main."""
    await run_server(SOURCE, HTTP_PORT, IgdDevice)


if __name__ == "__main__":
    asyncio.run(async_main())
