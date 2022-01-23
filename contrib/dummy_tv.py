#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Dummy TV supporting DLNA/DMR."""
# Instructions:
# - Change `SOURCE``. When using IPv6, be sure to set the scope_id, the last value in the tuple.
# - Run this module.
# - Run upnp-client (change IP to your own IP):
#    upnp-client call-action 'http://0.0.0.0:8000/device.xml' \
#                RC/GetVolume InstanceID=0 Channel=Master

import asyncio
import logging
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
LOGGER = logging.getLogger("dummy_tv")
LOGGER_SSDP_TRAFFIC = logging.getLogger("async_upnp_client.traffic")
LOGGER_SSDP_TRAFFIC.setLevel(logging.WARNING)
SOURCE = ("0.0.0.0", 0)  # Your IP here!
HTTP_PORT = 8000


class MediaRendererDevice(UpnpServerDevice):
    """Media Renderer device."""

    DEVICE_DEFINITION = DeviceInfo(
        device_type="urn:schemas-upnp-org:device:MediaRenderer:1",
        friendly_name="Dummy TV",
        manufacturer="Steven",
        model_name="DummyTV v1",
        udn="uuid:ea2181c0-c677-4a09-80e6-f9e69a951284",
        model_description="Dummy TV DMR",
        model_number="v0.0.1",
        serial_number="0000001",
        url="/device.xml",
        icons=[],
        xml=ET.Element("server_device"),
    )

    def __init__(self, requester: UpnpRequester, base_uri: str) -> None:
        """Initialize."""
        services = [
            RenderingControlService(requester=requester),
            AVTransportService(requester=requester),
            ConnectionManagerService(requester=requester),
        ]
        super().__init__(
            requester=requester,
            base_uri=base_uri,
            services=services,
            embedded_devices=[],
        )


class RenderingControlService(UpnpServerService):
    """Rendering Control service."""

    SERVICE_DEFINITION = ServiceInfo(
        service_id="urn:upnp-org:serviceId:RenderingControl",
        service_type="urn:schemas-upnp-org:service:RenderingControl:1",
        control_url="/upnp/control/RenderingControl1",
        event_sub_url="/upnp/event/RenderingControl1",
        scpd_url="/RenderingControl_1.xml",
        xml=ET.Element("server_service"),
    )

    STATE_VARIABLE_DEFINITIONS = {
        "Volume": StateVariableTypeInfo(
            data_type="ui2",
            data_type_mapping=STATE_VARIABLE_TYPE_MAPPING["ui2"],
            default_value="0",
            allowed_value_range={
                "min": "0",
                "max": "100",
            },
            allowed_values=None,
            xml=ET.Element("server_stateVariable"),
        ),
        "Mute": StateVariableTypeInfo(
            data_type="boolean",
            data_type_mapping=STATE_VARIABLE_TYPE_MAPPING["boolean"],
            default_value="0",
            allowed_value_range={},
            allowed_values=["0", "1", ],
            xml=ET.Element("server_stateVariable"),
        ),
        "A_ARG_TYPE_InstanceID": StateVariableTypeInfo(
            data_type="ui4",
            data_type_mapping=STATE_VARIABLE_TYPE_MAPPING["ui4"],
            default_value=None,
            allowed_value_range={},
            allowed_values=None,
            xml=ET.Element("server_stateVariable"),
        ),
        "A_ARG_TYPE_Channel": StateVariableTypeInfo(
            data_type="string",
            data_type_mapping=STATE_VARIABLE_TYPE_MAPPING["string"],
            default_value=None,
            allowed_value_range={},
            allowed_values=None,
            xml=ET.Element("server_stateVariable"),
        ),
    }

    @callable_action(
        name="GetVolume",
        in_args={
            "InstanceID": "A_ARG_TYPE_InstanceID",
            "Channel": "A_ARG_TYPE_Channel",
        },
        out_args={
            "CurrentVolume": "Volume",
        },
    )
    async def get_volume(
        self, InstanceID: int, Channel: str
    ) -> Dict[str, UpnpStateVariable]:
        """Get Volume."""
        # pylint: disable=invalid-name, unused-argument
        return {
            "CurrentVolume": self.state_variable("Volume"),
        }

    @callable_action(
        name="SetVolume",
        in_args={
            "InstanceID": "A_ARG_TYPE_InstanceID",
            "Channel": "A_ARG_TYPE_Channel",
            "DesiredVolume": "Volume",
        },
        out_args={},
    )
    async def set_volume(
        self, InstanceID: int, Channel: str, DesiredVolume: int
    ) -> Dict[str, UpnpStateVariable]:
        """Set Volume."""
        # pylint: disable=invalid-name, unused-argument
        volume = self.state_variable("Volume")
        volume.value = DesiredVolume
        return {}

    @callable_action(
        name="GetMute",
        in_args={
            "InstanceID": "A_ARG_TYPE_InstanceID",
            "Channel": "A_ARG_TYPE_Channel",
        },
        out_args={
            "CurrentMute": "Mute",
        },
    )
    async def get_mute(
        self, InstanceID: int, Channel: str
    ) -> Dict[str, UpnpStateVariable]:
        """Get Mute."""
        # pylint: disable=invalid-name, unused-argument
        return {
            "CurrentMute": self.state_variable("Mute"),
        }

    @callable_action(
        name="SetMute",
        in_args={
            "InstanceID": "A_ARG_TYPE_InstanceID",
            "Channel": "A_ARG_TYPE_Channel",
            "DesiredMute": "Mute",
        },
        out_args={},
    )
    async def set_mute(
        self, InstanceID: int, Channel: str, DesiredMute: bool
    ) -> Dict[str, UpnpStateVariable]:
        """Set Volume."""
        # pylint: disable=invalid-name, unused-argument
        volume = self.state_variable("Mute")
        volume.value = DesiredMute
        return {}


class AVTransportService(UpnpServerService):
    """AVTransport service."""

    SERVICE_DEFINITION = ServiceInfo(
        service_id="urn:upnp-org:serviceId:AVTransport",
        service_type="urn:schemas-upnp-org:service:AVTransport:1",
        control_url="/upnp/control/AVTransport1",
        event_sub_url="/upnp/event/AVTransport1",
        scpd_url="/AVTransport_1.xml",
        xml=ET.Element("server_service"),
    )

    STATE_VARIABLE_DEFINITIONS = {
        "A_ARG_TYPE_InstanceID": StateVariableTypeInfo(
            data_type="ui4",
            data_type_mapping=STATE_VARIABLE_TYPE_MAPPING["ui4"],
            default_value=None,
            allowed_value_range={},
            allowed_values=None,
            xml=ET.Element("server_stateVariable"),
        ),
        "CurrentTrackURI": StateVariableTypeInfo(
            data_type="string",
            data_type_mapping=STATE_VARIABLE_TYPE_MAPPING["string"],
            default_value="",
            allowed_value_range={},
            allowed_values=None,
            xml=ET.Element("server_stateVariable"),
        ),
        "CurrentTrack": StateVariableTypeInfo(
            data_type="ui4",
            data_type_mapping=STATE_VARIABLE_TYPE_MAPPING["ui4"],
            default_value=None,
            allowed_value_range={},
            allowed_values=None,
            xml=ET.Element("server_stateVariable"),
        ),
        "AVTransportURI": StateVariableTypeInfo(
            data_type="string",
            data_type_mapping=STATE_VARIABLE_TYPE_MAPPING["string"],
            default_value="",
            allowed_value_range={},
            allowed_values=None,
            xml=ET.Element("server_stateVariable"),
        ),
        "TransportState": StateVariableTypeInfo(
            data_type="string",
            data_type_mapping=STATE_VARIABLE_TYPE_MAPPING["string"],
            default_value="STOPPED",
            allowed_value_range={},
            allowed_values=["STOPPED", "PLAYING", "PAUSED_PLAYBACK", "TRANSITIONING", ],
            xml=ET.Element("server_stateVariable"),
        ),
        "TransportStatus": StateVariableTypeInfo(
            data_type="string",
            data_type_mapping=STATE_VARIABLE_TYPE_MAPPING["string"],
            default_value="",
            allowed_value_range={},
            allowed_values=None,
            xml=ET.Element("server_stateVariable"),
        ),
        "TransportPlaySpeed": StateVariableTypeInfo(
            data_type="string",
            data_type_mapping=STATE_VARIABLE_TYPE_MAPPING["string"],
            default_value="1",
            allowed_value_range={},
            allowed_values=["1"],
            xml=ET.Element("server_stateVariable"),
        ),
        "PossiblePlaybackStorageMedia": StateVariableTypeInfo(
            data_type="string",
            data_type_mapping=STATE_VARIABLE_TYPE_MAPPING["string"],
            default_value="NOT_IMPLEMENTED",
            allowed_value_range={},
            allowed_values=["NOT_IMPLEMENTED"],
            xml=ET.Element("server_stateVariable"),
        ),
        "PossibleRecordStorageMedia": StateVariableTypeInfo(
            data_type="string",
            data_type_mapping=STATE_VARIABLE_TYPE_MAPPING["string"],
            default_value="NOT_IMPLEMENTED",
            allowed_value_range={},
            allowed_values=["NOT_IMPLEMENTED"],
            xml=ET.Element("server_stateVariable"),
        ),
        "PossibleRecordQualityModes": StateVariableTypeInfo(
            data_type="string",
            data_type_mapping=STATE_VARIABLE_TYPE_MAPPING["string"],
            default_value="NOT_IMPLEMENTED",
            allowed_value_range={},
            allowed_values=["NOT_IMPLEMENTED"],
            xml=ET.Element("server_stateVariable"),
        ),
        "CurrentPlayMode": StateVariableTypeInfo(
            data_type="string",
            data_type_mapping=STATE_VARIABLE_TYPE_MAPPING["string"],
            default_value="NORMAL",
            allowed_value_range={},
            allowed_values=["NORMAL"],
            xml=ET.Element("server_stateVariable"),
        ),
        "CurrentRecordQualityMode": StateVariableTypeInfo(
            data_type="string",
            data_type_mapping=STATE_VARIABLE_TYPE_MAPPING["string"],
            default_value="NOT_IMPLEMENTED",
            allowed_value_range={},
            allowed_values=["NOT_IMPLEMENTED"],
            xml=ET.Element("server_stateVariable"),
        ),
    }

    @callable_action(
        name="GetTransportInfo",
        in_args={
            "InstanceID": "A_ARG_TYPE_InstanceID",
        },
        out_args={
            "CurrentTransportState": "TransportState",
            "CurrentTransportStatus": "TransportStatus",
            "CurrentSpeed": "TransportPlaySpeed",
        },
    )
    async def get_transport_info(self, InstanceID: int) -> Dict[str, UpnpStateVariable]:
        """Get Transport Info."""
        # pylint: disable=invalid-name, unused-argument
        return {
            "CurrentTransportState": self.state_variable("TransportState"),
            "CurrentTransportStatus": self.state_variable("TransportStatus"),
            "CurrentSpeed": self.state_variable("TransportPlaySpeed"),
        }

    @callable_action(
        name="GetMediaInfo",
        in_args={
            "InstanceID": "A_ARG_TYPE_InstanceID",
        },
        out_args={
            "CurrentURI": "AVTransportURI",
        },
    )
    async def get_media_info(self, InstanceID: int) -> Dict[str, UpnpStateVariable]:
        """Get Media Info."""
        # pylint: disable=invalid-name, unused-argument
        return {
            "CurrentURI": self.state_variable("AVTransportURI"),
        }

    @callable_action(
        name="GetDeviceCapabilities",
        in_args={
            "InstanceID": "A_ARG_TYPE_InstanceID",
        },
        out_args={
            "PlayMedia": "PossiblePlaybackStorageMedia",
            "RecMedia": "PossibleRecordStorageMedia",
            "RecQualityModes": "PossibleRecordQualityModes",
        },
    )
    async def get_device_capabilities(self, InstanceID: int) -> Dict[str, UpnpStateVariable]:
        """Get Device Capabilities."""
        # pylint: disable=invalid-name, unused-argument
        return {
            "PlayMedia": self.state_variable("PossiblePlaybackStorageMedia"),
            "RecMedia": self.state_variable("PossibleRecordStorageMedia"),
            "RecQualityModes": self.state_variable("PossibleRecordQualityModes"),
        }

    @callable_action(
        name="GetTransportSettings",
        in_args={
            "InstanceID": "A_ARG_TYPE_InstanceID",
        },
        out_args={
            "PlayMode": "CurrentPlayMode",
            "RecQualityMode": "CurrentRecordQualityMode",
        },
    )
    async def get_transport_settings(self, InstanceID: int) -> Dict[str, UpnpStateVariable]:
        """Get Transport Settings."""
        # pylint: disable=invalid-name, unused-argument
        return {
            "PlayMode": self.state_variable("CurrentPlayMode"),
            "RecQualityMode": self.state_variable("CurrentRecordQualityMode"),
        }


class ConnectionManagerService(UpnpServerService):
    """ConnectionManager service."""

    SERVICE_DEFINITION = ServiceInfo(
        service_id="urn:upnp-org:serviceId:ConnectionManager",
        service_type="urn:schemas-upnp-org:service:ConnectionManager:1",
        control_url="/upnp/control/ConnectionManager1",
        event_sub_url="/upnp/event/ConnectionManager1",
        scpd_url="/ConnectionManager_1.xml",
        xml=ET.Element("server_service"),
    )

    STATE_VARIABLE_DEFINITIONS = {
        "A_ARG_TYPE_InstanceID": StateVariableTypeInfo(
            data_type="ui4",
            data_type_mapping=STATE_VARIABLE_TYPE_MAPPING["ui4"],
            default_value=None,
            allowed_value_range={},
            allowed_values=None,
            xml=ET.Element("server_stateVariable"),
        ),
    }


async def async_main() -> None:
    """Main."""
    await run_server(SOURCE, HTTP_PORT, MediaRendererDevice)


if __name__ == "__main__":
    asyncio.run(async_main())
