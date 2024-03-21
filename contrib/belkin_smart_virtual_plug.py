#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Virtual/Emulated Belkin Switch."""
# Instructions:
# - The script will use your default route network interface IP as `SOURCE`, so if needed change the `SOURCE`
#     When using IPv6, be sure to set the scope_id, the last value in the tuple.
# Author: Helvio Junior @helviojunior

import asyncio
import logging
import socket
import xml.etree.ElementTree as ET
from time import time
from typing import Dict, Sequence, Type

from async_upnp_client.client import UpnpRequester, UpnpStateVariable
from async_upnp_client.const import (
    STATE_VARIABLE_TYPE_MAPPING,
    DeviceInfo,
    ServiceInfo,
    StateVariableTypeInfo, EventableStateVariableTypeInfo,
)

from async_upnp_client.server import UpnpServer, UpnpServerDevice, UpnpServerService, callable_action, \
    UpnpEventableStateVariable, EventSubscriber, create_state_var

logging.basicConfig(level=logging.DEBUG)
LOGGER = logging.getLogger("emulated_device")
LOGGER_SSDP_TRAFFIC = logging.getLogger("async_upnp_client.traffic")
LOGGER_SSDP_TRAFFIC.setLevel(logging.WARNING)
SOURCE = ("127.0.0.1", 0)  # The script will set dynamically
# SOURCE = ("fe80::215:5dff:fe3e:6d23", 0, 0, 6)  # Your IP here!
HTTP_PORT = 1900


class EventService(UpnpServerService):
    """Rendering Control service."""

    SERVICE_DEFINITION = ServiceInfo(
        service_id="urn:Belkin:serviceId:basicevent1",
        service_type="urn:Belkin:service:basicevent:1",
        control_url="/upnp/control/basicevent1",
        event_sub_url="/upnp/event/basicevent1",
        scpd_url="/eventservice.xml",
        xml=ET.Element("server_service"),
    )

    STATE_VARIABLE_DEFINITIONS = {
        "BinaryState": EventableStateVariableTypeInfo(
            data_type="boolean",
            data_type_mapping=STATE_VARIABLE_TYPE_MAPPING["boolean"],
            default_value="0",
            allowed_value_range={},
            max_rate=0,  # seconds
            allowed_values=[
                "0",
                "1",
            ],
            xml=ET.Element("server_stateVariable"),
        ),
    }

    def __init__(self, requester: UpnpRequester) -> None:
        """Initialize."""
        super().__init__(requester)

    @callable_action(
        name="GetBinaryState",
        in_args={
            "BinaryState": "BinaryState",
        },
        out_args={
            "BinaryState": "BinaryState",
        },
    )
    async def get_binary_state(
        self, BinaryState: bool
    ) -> Dict[str, UpnpStateVariable]:
        """Get Binary State."""
        # pylint: disable=invalid-name, unused-argument
        return {
            "BinaryState": self.state_variable("BinaryState"),
        }

    @callable_action(
        name="SetBinaryState",
        in_args={
            "BinaryState": "BinaryState",
        },
        out_args={},
    )
    async def set_binary_state(
        self, BinaryState: bool
    ) -> Dict[str, UpnpStateVariable]:
        """Set Binary State."""
        # pylint: disable=invalid-name, unused-argument
        binaryState = self.state_variable("BinaryState")
        binaryState.value = BinaryState

        LOGGER.warning(f'BinaryState changed: {BinaryState}')

        return {}


class AlexaVirtualDevice(UpnpServerDevice):
    """Virtual Switch device."""

    DEVICE_DEFINITION = DeviceInfo(
        device_type="urn:Belkin:device:controllee:1",  # Do Not change
        friendly_name="Test device",
        manufacturer="Belkin International Inc.",
        manufacturer_url="http://www.belkin.com",
        udn="uuid:Socket-1_0-221517K0101769",
        upc="123456789",
        model_name="Socket",   # Do Not change
        model_description="Belkin Plugin Socket 1.0",
        model_number="1.0",
        model_url="http://www.belkin.com/plugin",
        serial_number="221517K0101769",
        presentation_url=None,
        url="/setup.xml",
        icons=[],
        xml=ET.Element("server_device"),
    )

    EMBEDDED_DEVICES: Sequence[Type[UpnpServerDevice]] = []
    SERVICES = [EventService]

    def __init__(self, requester: UpnpRequester, base_uri: str, boot_id: int, config_id: int) -> None:
        """Initialize."""

        super().__init__(
            requester=requester,
            base_uri=base_uri,
            boot_id=boot_id,
            config_id=config_id,
        )


async def async_main(server: UpnpServer) -> None:
    """Main."""
    await server.async_start()

    while True:
        await asyncio.sleep(3600)


async def async_stop(server: UpnpServer) -> None:
    await server.async_stop()

    loop = asyncio.get_event_loop()
    loop.run_until_complete()


def set_ip_address():
    global SOURCE
    temp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        temp_socket.connect(('8.8.8.8', 53))
        SOURCE = (temp_socket.getsockname()[0], 0)
    except:
        SOURCE = ('127.0.0.1', 0)
    del temp_socket


if __name__ == "__main__":
    boot_id = int(time())
    config_id = 1
    set_ip_address()
    server = UpnpServer(AlexaVirtualDevice, SOURCE, http_port=HTTP_PORT, boot_id=boot_id, config_id=config_id)

    try:
        asyncio.run(async_main(server))
    except KeyboardInterrupt:
        print(KeyboardInterrupt)

    asyncio.run(server.async_stop())
