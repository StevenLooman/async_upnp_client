#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Dummy mediaseerver."""
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
    EventableStateVariableTypeInfo,
)

from async_upnp_client.server import UpnpServer, UpnpServerDevice, UpnpServerService, callable_action

logging.basicConfig(level=logging.DEBUG)
LOGGER = logging.getLogger("dummy_mediaserver")
LOGGER_SSDP_TRAFFIC = logging.getLogger("async_upnp_client.traffic")
LOGGER_SSDP_TRAFFIC.setLevel(logging.WARNING)
SOURCE = ("192.168.1.85", 0)  # Your IP here!
# SOURCE = ("fe80::215:5dff:fe3e:6d23", 0, 0, 6)  # Your IP here!
HTTP_PORT = 8000


class ContentDirectoryService(UpnpServerService):
    """DLNA Content Directory."""

    SERVICE_DEFINITION = ServiceInfo(
        service_id="urn:upnp-org:serviceId:ContentDirectory",
        service_type="urn:schemas-upnp-org:service:ContentDirectory:2",
        control_url="/upnp/control/ContentDirectory",
        event_sub_url="/upnp/event/ContentDirectory",
        scpd_url="/ContentDirectory.xml",
        xml=ET.Element("server_service"),
    )

    STATE_VARIABLE_DEFINITIONS = {
        "SearchCapabilities": StateVariableTypeInfo(
            data_type="string",
            data_type_mapping=STATE_VARIABLE_TYPE_MAPPING["string"],
            default_value="",
            allowed_value_range={},
            allowed_values=None,
            xml=ET.Element("server_stateVariable"),
            ),
        "SortCapabilities": StateVariableTypeInfo(
            data_type="string",
            data_type_mapping=STATE_VARIABLE_TYPE_MAPPING["string"],
            default_value="",
            allowed_value_range={},
            allowed_values=None,
            xml=ET.Element("server_stateVariable"),
            ),
        "SystemUpdateID": EventableStateVariableTypeInfo(
            data_type="ui4",
            data_type_mapping=STATE_VARIABLE_TYPE_MAPPING["ui4"],
            default_value=0,
            allowed_value_range={},
            allowed_values=None,
            max_rate=None,
            xml=ET.Element("server_stateVariable"),
            ),
        "FeatureList": StateVariableTypeInfo(
            data_type="string",
            data_type_mapping=STATE_VARIABLE_TYPE_MAPPING["string"],
            default_value="""<?xml version="1.0" encoding="UTF-8"?>
<Features
 xmlns="urn:schemas-upnp-org:av:avs"
 xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
 xsi:schemaLocation="
 urn:schemas-upnp-org:av:avs
 http://www.upnp.org/schemas/av/avs-v1-20060531.xsd">
</Features>""",
            allowed_value_range={},
            allowed_values=None,
            xml=ET.Element("server_stateVariable"),
            ),
        "A_ARG_TYPE_BrowseFlag": StateVariableTypeInfo(
            data_type="string",
            data_type_mapping=STATE_VARIABLE_TYPE_MAPPING["string"],
            default_value=None,
            allowed_value_range={},
            allowed_values=["BrowseMetadata", "BrowseDirectChildren"],
            xml=ET.Element("server_stateVariable"),
            ),
        "A_ARG_TYPE_Filter": StateVariableTypeInfo(
            data_type="string",
            data_type_mapping=STATE_VARIABLE_TYPE_MAPPING["string"],
            default_value=None,
            allowed_value_range={},
            allowed_values=None,
            xml=ET.Element("server_stateVariable"),
            ),
        "A_ARG_TYPE_ObjectID": StateVariableTypeInfo(
            data_type="string",
            data_type_mapping=STATE_VARIABLE_TYPE_MAPPING["string"],
            default_value=None,
            allowed_value_range={},
            allowed_values=None,
            xml=ET.Element("server_stateVariable"),
        ),
        "A_ARG_TYPE_Count": StateVariableTypeInfo(
            data_type="ui4",
            data_type_mapping=STATE_VARIABLE_TYPE_MAPPING["ui4"],
            default_value=None,
            allowed_value_range={},
            allowed_values=None,
            xml=ET.Element("server_stateVariable"),
        ),
        "A_ARG_TYPE_Index": StateVariableTypeInfo(
            data_type="ui4",
            data_type_mapping=STATE_VARIABLE_TYPE_MAPPING["ui4"],
            default_value=None,
            allowed_value_range={},
            allowed_values=None,
            xml=ET.Element("server_stateVariable"),
        ),
        "A_ARG_TYPE_SortCriteria": StateVariableTypeInfo(
            data_type="string",
            data_type_mapping=STATE_VARIABLE_TYPE_MAPPING["string"],
            default_value=None,
            allowed_value_range={},
            allowed_values=None,
            xml=ET.Element("server_stateVariable"),
            ),
        ###
        "A_ARG_TYPE_Result": StateVariableTypeInfo(
            data_type="string",
            data_type_mapping=STATE_VARIABLE_TYPE_MAPPING["string"],
            default_value=None,
            allowed_value_range={},
            allowed_values=None,
            xml=ET.Element("server_stateVariable"),
            ),
        "A_ARG_TYPE_UpdateID": StateVariableTypeInfo(
            data_type="ui4",
            data_type_mapping=STATE_VARIABLE_TYPE_MAPPING["ui4"],
            default_value=None,
            allowed_value_range={},
            allowed_values=None,
            xml=ET.Element("server_stateVariable"),
            ),
        "A_ARG_TYPE_Count_NumberReturned": StateVariableTypeInfo(
            data_type="ui4",
            data_type_mapping=STATE_VARIABLE_TYPE_MAPPING["ui4"],
            default_value=None,
            allowed_value_range={},
            allowed_values=None,
            xml=ET.Element("server_stateVariable"),
        ),
        "A_ARG_TYPE_Count_TotalMatches": StateVariableTypeInfo(
            data_type="ui4",
            data_type_mapping=STATE_VARIABLE_TYPE_MAPPING["ui4"],
            default_value=None,
            allowed_value_range={},
            allowed_values=None,
            xml=ET.Element("server_stateVariable"),
        ),
    }

    @callable_action(
        name="Browse",
        in_args={
            "BrowseFlag": "A_ARG_TYPE_BrowseFlag",
            "Filter": "A_ARG_TYPE_Filter",
            "ObjectID": "A_ARG_TYPE_ObjectID",
            "RequestedCount": "A_ARG_TYPE_Count",
            "SortCriteria": "A_ARG_TYPE_SortCriteria",
            "StartingIndex": "A_ARG_TYPE_Index",
            },
        out_args={
            "Result": "A_ARG_TYPE_Result",
            "NumberReturned": "A_ARG_TYPE_Count_NumberReturned",
            "TotalMatches": "A_ARG_TYPE_Count_TotalMatches",
            "UpdateID": "A_ARG_TYPE_UpdateID",
        },
    )
    async def browse(self, BrowseFlag: str, Filter: str, ObjectID: str, StartingIndex: int,
                     RequestedCount: int, SortCriteria: str) -> Dict[str, UpnpStateVariable]:
        """Browse media."""
        self.state_variable("A_ARG_TYPE_Result").value = "Some Value"
        self.state_variable("A_ARG_TYPE_Count_NumberReturned").value = 1
        self.state_variable("A_ARG_TYPE_Count_TotalMatches").value = 2
        self.state_variable("A_ARG_TYPE_UpdateID").value = 3
        return {
            "Result": self.state_variable("A_ARG_TYPE_Result"),
            "NumberReturned": self.state_variable("A_ARG_TYPE_Count_NumberReturned"),
            "TotalMatches": self.state_variable("A_ARG_TYPE_Count_TotalMatches"),
            "UpdateID": self.state_variable("A_ARG_TYPE_UpdateID"),
        }

    @callable_action(
        name="GetSearchCapabilities",
        in_args={},
        out_args={
            "SearchCaps": "SearchCapabilities",
        },
    )
    async def GetSearchCapabilities(self) -> Dict[str, UpnpStateVariable]:
        """Browse media."""
        return {
            "SearchCaps": self.state_variable("SearchCapabilities"),
        }

    @callable_action(
        name="GetSortCapabilities",
        in_args={},
        out_args={
            "SortCaps": "SortCapabilities",
        },
    )
    async def GetSortCapabilities(self) -> Dict[str, UpnpStateVariable]:
        """Browse media."""
        return {
            "SortCaps": self.state_variable("SortCapabilities"),
        }
    @callable_action(
        name="GetFeatureList",
        in_args={},
        out_args={
            "FeatureList": "FeatureList",
        },
    )
    async def GetFeatureList(self) -> Dict[str, UpnpStateVariable]:
        """Browse media."""
        return {
            "FeatureList": self.state_variable("FeatureList"),
        }
    @callable_action(
        name="GetSystemUpdateID",
        in_args={},
        out_args={
            "Id": "SystemUpdateID",
        },
    )
    async def GetSystemUpdateID(self) -> Dict[str, UpnpStateVariable]:
        """Browse media."""
        return {
            "Id": self.state_variable("SystemUpdateID"),
        }


class MediaServerDevice(UpnpServerDevice):
    """Media Server Device."""

    DEVICE_DEFINITION = DeviceInfo(
        device_type=":urn:schemas-upnp-org:device:MediaServer:2",
        friendly_name="Media Server v1",
        manufacturer="Steven",
        manufacturer_url=None,
        model_name="MediaServer v1",
        model_url=None,
        udn="uuid:1cd38bfe-3c10-403e-a97f-2bc5c1652b9a",
        upc=None,
        model_description="Media Server",
        model_number="v0.0.1",
        serial_number="0000001",
        presentation_url=None,
        url="/device.xml",
        icons=[],
        xml=ET.Element("server_device"),
    )
    EMBEDDED_DEVICES = []
    SERVICES = [ContentDirectoryService]

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


if __name__ == "__main__":
    boot_id = int(time())
    config_id = 1
    server = UpnpServer(MediaServerDevice, SOURCE, http_port=HTTP_PORT, boot_id=boot_id, config_id=config_id)

    try:
        asyncio.run(async_main(server))
    except KeyboardInterrupt:
        print(KeyboardInterrupt)

    asyncio.run(server.async_stop())
