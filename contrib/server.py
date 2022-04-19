# -*- coding: utf-8 -*-
"""UPnP Server."""
import asyncio
import logging
import xml.etree.ElementTree as ET
from asyncio.transports import DatagramTransport
from functools import partial, wraps
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Mapping,
    Optional,
    Sequence,
    Tuple,
    Type,
    Union,
    cast,
)

import aiohttp.web
import defusedxml.ElementTree as DET  # pylint: disable=import-error

from async_upnp_client.client import (
    UpnpAction,
    UpnpDevice,
    UpnpError,
    UpnpRequester,
    UpnpService,
    UpnpStateVariable,
)
from async_upnp_client.client_factory import UpnpFactory
from async_upnp_client.const import (
    ActionArgumentInfo,
    ActionInfo,
    AddressTupleVXType,
    DeviceInfo,
    ServiceInfo,
    SsdpHeaders,
    StateVariableInfo,
    StateVariableTypeInfo,
)
from async_upnp_client.exceptions import (
    UpnpActionError,
    UpnpActionErrorCode,
    UpnpValueError,
)
from async_upnp_client.ssdp import (
    SSDP_DISCOVER,
    SSDP_TARGET_V4,
    SSDP_TARGET_V6,
    SsdpProtocol,
    build_ssdp_packet,
    determine_source_target,
    get_ssdp_socket,
)

NAMESPACES = {
    "s": "http://schemas.xmlsoap.org/soap/envelope/",
    "es": "http://schemas.xmlsoap.org/soap/encoding/",
}
LOGGER = logging.getLogger("async_upnp_client.server")


class SsdpSearchResponder:
    """SSDP SEARCH responder."""

    def __init__(
        self,
        device: "UpnpServerDevice",
        source: Optional[AddressTupleVXType] = None,
        target: Optional[AddressTupleVXType] = None,
    ) -> None:
        """Init the ssdp search responder class."""
        self.device = device
        self.source, self.target = determine_source_target(source, target)
        self._transport: Optional[DatagramTransport] = None

    async def _async_on_connect(self, transport: DatagramTransport) -> None:
        """Handle on connect."""
        self._transport = transport

    async def _async_on_data(
        self,
        request_line: str,
        headers: SsdpHeaders,
    ) -> None:
        """Handle data."""
        assert self._transport

        if request_line != "M-SEARCH * HTTP/1.1" or headers.get("MAN") != SSDP_DISCOVER:
            return

        remote_addr = headers["_remote_addr"]
        LOGGER.debug("Received M-SEARCH from: %s, headers: %s", remote_addr, headers)

        # 3 + 2d + k (d: embedded device, k: service)
        # global:      ST: upnp:rootdevice
        #              USN: uuid:device-UUID::upnp:rootdevice
        # per device : ST: uuid:device-UUID
        #              USN: uuid:device-UUID
        # per device : ST: urn:schemas-upnp-org:device:deviceType:ver
        #              USN: uuid:device-UUID::urn:schemas-upnp-org:device:deviceType:ver
        # per service: ST: urn:schemas-upnp-org:service:serviceType:ver
        #              USN: uuid:device-UUID::urn:schemas-upnp-org:service:serviceType:ver
        await self._async_send_response_rootdevice(remote_addr)
        for device in self.device.all_devices:
            await self._async_send_responses_device(remote_addr, device)
        for service in self.device.all_services:
            await self._async_send_responses_service(remote_addr, service)

    async def async_start(self) -> None:
        """Start."""
        LOGGER.debug("Start listening for search requests")

        # Construct a socket for use with this pairs of endpoints.
        sock, _sock_source, sock_target = get_ssdp_socket(self.source, self.target)
        LOGGER.debug("Binding to address: %s", sock_target)
        sock.bind(sock_target)

        # Create protocol and send discovery packet.
        loop = asyncio.get_event_loop()
        await loop.create_datagram_endpoint(
            lambda: SsdpProtocol(
                loop,
                on_connect=self._async_on_connect,
                on_data=self._async_on_data,
            ),
            sock=sock,
        )

    async def async_stop(self) -> None:
        """Stop listening for advertisements."""
        assert self._transport

        LOGGER.debug("Stop listening for SEARCH requests")
        self._transport.close()

    async def _async_send_response_rootdevice(
        self, remote_addr: AddressTupleVXType
    ) -> None:
        """Send root device reponse."""
        await self._async_send_response(
            remote_addr, "upnp:rootdevice", f"{self.device.udn}::upnp:rootdevice"
        )

    async def _async_send_responses_device(
        self, remote_addr: AddressTupleVXType, device: UpnpDevice
    ) -> None:
        """Send device reponses."""
        await self._async_send_response(remote_addr, device.udn, f"{self.device.udn}")
        await self._async_send_response(
            remote_addr, device.device_type, f"{self.device.udn}::{device.device_type}"
        )

    async def _async_send_responses_service(
        self, remote_addr: AddressTupleVXType, service: UpnpService
    ) -> None:
        """Send service reponses."""
        await self._async_send_response(
            remote_addr,
            service.service_type,
            f"{self.device.udn}::{service.service_type}",
        )

    async def _async_send_response(
        self,
        remote_addr: AddressTupleVXType,
        service_type: str,
        unique_service_name: str,
    ) -> None:
        """Send a response."""
        assert self._transport

        response_headers = {
            "CACHE-CONTROL": "max-age=150",
            "SERVER": "async-upnp-client/1.0 UPnP/1.0 DummyServer/1.0",
            "ST": service_type,
            "USN": unique_service_name,
            "EXT": "",
            "LOCATION": f"{self.device.base_uri}{self.device.device_url}",
        }

        response_line = "HTTP/1.1 200 OK"
        protocol = cast(SsdpProtocol, self._transport.get_protocol())
        packet = build_ssdp_packet(response_line, response_headers)
        LOGGER.debug(
            "Sending search response, ST: %s, USN: %s, ",
            response_headers["ST"],
            response_headers["USN"],
        )
        protocol.send_ssdp_packet(packet, remote_addr)


def _build_advertisements(root_device: "UpnpServerDevice") -> List[SsdpHeaders]:
    """Build advertisements to be sent for a UpnpDevice."""
    # 3 + 2d + k (d: embedded device, k: service)
    # global:      ST: upnp:rootdevice
    #              USN: uuid:device-UUID::upnp:rootdevice
    # per device : ST: uuid:device-UUID
    #              USN: uuid:device-UUID
    # per device : ST: urn:schemas-upnp-org:device:deviceType:ver
    #              USN: uuid:device-UUID::urn:schemas-upnp-org:device:deviceType:ver
    # per service: ST: urn:schemas-upnp-org:service:serviceType:ver
    #              USN: uuid:device-UUID::urn:schemas-upnp-org:service:serviceType:ver
    advertisements: List[SsdpHeaders] = []

    base_headers = {
        "NTS": "ssdp:alive",
        "SERVER": "async-upnp-client/1.0 UPnP/2.0 DummyServer/1.0",
        "BOOTID.UPNP.ORG": "1",
        "CONFIGID.UPNP.ORG": "1",
        "LOCATION": f"{root_device.base_uri}{root_device.device_url}",
    }

    # root device
    advertisements.append(
        {
            **base_headers,
            "NT": "upnp:rootdevice",
            "USN": f"{root_device.udn}::upnp:rootdevice",
        }
    )

    for device in root_device.all_devices:
        advertisements.append(
            {
                **base_headers,
                "NT": f"{device.udn}",
                "USN": f"{device.udn}",
            }
        )
        advertisements.append(
            {
                **base_headers,
                "NT": f"{device.device_type}",
                "USN": f"{device.udn}::{device.device_type}",
            }
        )

    for service in root_device.all_services:
        advertisements.append(
            {
                **base_headers,
                "NT": f"{service.service_type}",
                "USN": f"{service.device.udn}::{service.service_type}",
            }
        )

    return advertisements


class SsdpAdvertisementAnnouncer:
    """SSDP Advertisement announcer."""

    def __init__(
        self,
        device: "UpnpServerDevice",
        source: Optional[AddressTupleVXType] = None,
        target: Optional[AddressTupleVXType] = None,
    ) -> None:
        """Init the ssdp search responder class."""
        self.device = device
        self.source, self.target = determine_source_target(source, target)
        self._transport: Optional[DatagramTransport] = None

        self._advertisements = _build_advertisements(device)
        self._advertisement_index = 0

    async def _async_on_connect(self, transport: DatagramTransport) -> None:
        """Handle on connect."""
        self._transport = transport

    async def async_start(self) -> None:
        """Start."""
        LOGGER.debug("Start advertisements announcer")

        # Construct a socket for use with this pairs of endpoints.
        sock, _sock_source, sock_target = get_ssdp_socket(self.source, self.target)
        LOGGER.debug("Binding to address: %s", sock_target)
        sock.bind(sock_target)

        # Create protocol and send discovery packet.
        loop = asyncio.get_event_loop()
        await loop.create_datagram_endpoint(
            lambda: SsdpProtocol(
                loop,
                on_connect=self._async_on_connect,
            ),
            sock=sock,
        )

        # Reschedule self.
        self._announce_next()

    async def async_stop(self) -> None:
        """Stop listening for advertisements."""
        assert self._transport

        LOGGER.debug("Stop advertisements announcer")

        self._send_byebye()
        self._transport.close()

    def _announce_next(self) -> None:
        """Announce next advertisement."""
        assert self._transport

        start_line = "NOTIFY * HTTP/1.1"
        headers = self._advertisements[self._advertisement_index]
        self._advertisement_index = (self._advertisement_index + 1) % len(
            self._advertisements
        )

        packet = build_ssdp_packet(start_line, headers)
        protocol = cast(SsdpProtocol, self._transport.get_protocol())
        LOGGER.debug(
            "Sending advertisement, NTS: %s, NT: %s, USN: %s",
            headers["NTS"],
            headers["NT"],
            headers["USN"],
        )
        protocol.send_ssdp_packet(packet, self.target)

        # Reschedule self.
        loop = asyncio.get_event_loop()
        loop.call_later(30, self._announce_next)

    def _send_byebye(self) -> None:
        """Send ssdp:byebye."""
        assert self._transport

        start_line = "NOTIFY * HTTP/1.1"
        headers = {
            "NTS": "ssdp:byebye",
            "SERVER": "async-upnp-client/1.0 UPnP/2.0 DummyServer/1.0",
            # "BOOTID.UPNP.ORG": "1",
            # "CONFIGID.UPNP.ORG": "1",
            "NT": "upnp:rootdevice",
            "USN": f"{self.device.udn}::upnp:rootdevice",
            "LOCATION": f"{self.device.base_uri}{self.device.device_url}",
        }
        packet = build_ssdp_packet(start_line, headers)
        protocol = cast(SsdpProtocol, self._transport.get_protocol())
        LOGGER.debug(
            "Sending advertisement, NTS: %s, NT: %s, USN: %s",
            headers["NTS"],
            headers["NT"],
            headers["USN"],
        )
        protocol.send_ssdp_packet(packet, self.target)


class UpnpXmlSerializer:
    """Helper class to create device/service description from UpnpDevice/UpnpService."""

    # pylint: disable=too-few-public-methods

    @classmethod
    def to_xml(cls, thing: Union[UpnpDevice, UpnpService]) -> ET.Element:
        """Convert thing to XML."""
        if isinstance(thing, UpnpDevice):
            return cls._device_to_xml(thing)
        if isinstance(thing, UpnpService):
            return cls._service_to_xml(thing)

        raise NotImplementedError()

    @classmethod
    def _device_to_xml(cls, device: UpnpDevice) -> ET.Element:
        """Convert device to device description XML."""
        root_el = ET.Element("root", xmlns="urn:schemas-upnp-org:device-1-0")
        spec_version_el = ET.SubElement(root_el, "specVersion")
        ET.SubElement(spec_version_el, "major").text = "1"
        ET.SubElement(spec_version_el, "minor").text = "0"

        device_el = cls._device_to_xml_bare(device)
        root_el.append(device_el)

        return root_el

    @classmethod
    def _device_to_xml_bare(cls, device: UpnpDevice) -> ET.Element:
        """Convert device to XML, without the root-element."""
        device_el = ET.Element("device", xmlns="urn:schemas-upnp-org:device-1-0")
        ET.SubElement(device_el, "deviceType").text = device.device_type
        ET.SubElement(device_el, "friendlyName").text = device.friendly_name
        ET.SubElement(device_el, "manufacturer").text = device.manufacturer
        ET.SubElement(device_el, "modelDescription").text = device.model_description
        ET.SubElement(device_el, "modelName").text = device.model_name
        ET.SubElement(device_el, "modelNumber").text = device.model_number
        ET.SubElement(device_el, "serialNumber").text = device.serial_number
        ET.SubElement(device_el, "UDN").text = device.udn

        icon_list_el = ET.SubElement(device_el, "iconList")
        for icon in device.icons:
            icon_el = ET.SubElement(icon_list_el, "icon")
            ET.SubElement(icon_el, "mimetype").text = icon.mimetype
            ET.SubElement(icon_el, "width").text = str(icon.width)
            ET.SubElement(icon_el, "height").text = str(icon.height)
            ET.SubElement(icon_el, "depth").text = str(icon.depth)
            ET.SubElement(icon_el, "url").text = icon.url

        service_list_el = ET.SubElement(device_el, "serviceList")
        for service in device.services.values():
            service_el = ET.SubElement(service_list_el, "service")
            ET.SubElement(service_el, "serviceType").text = service.service_type
            ET.SubElement(service_el, "serviceId").text = service.service_id
            ET.SubElement(service_el, "controlURL").text = service.control_url
            ET.SubElement(service_el, "eventSubURL").text = service.event_sub_url
            ET.SubElement(service_el, "SCPDURL").text = service.scpd_url

        device_list_el = ET.SubElement(device_el, "deviceList")
        for embedded_device in device.embedded_devices.values():
            embedded_device_el = cls._device_to_xml_bare(embedded_device)
            device_list_el.append(embedded_device_el)

        return device_el

    @classmethod
    def _service_to_xml(cls, service: UpnpService) -> ET.Element:
        """Convert service to service description XML."""
        scpd_el = ET.Element("scpd", xmlns="urn:schemas-upnp-org:service-1-0")
        spec_version_el = ET.SubElement(scpd_el, "specVersion")
        ET.SubElement(spec_version_el, "major").text = "1"
        ET.SubElement(spec_version_el, "minor").text = "0"

        action_list_el = ET.SubElement(scpd_el, "actionList")
        for action in service.actions.values():
            action_el = cls._action_to_xml(action)
            action_list_el.append(action_el)

        state_table_el = ET.SubElement(scpd_el, "serviceStateTable")
        for state_var in service.state_variables.values():
            state_var_el = cls._state_variable_to_xml(state_var)
            state_table_el.append(state_var_el)

        return scpd_el

    @classmethod
    def _action_to_xml(cls, action: UpnpAction) -> ET.Element:
        """Convert action to service description XML."""
        action_el = ET.Element("action")
        ET.SubElement(action_el, "name").text = action.name

        if action.arguments:
            arg_list_el = ET.SubElement(action_el, "argumentList")
            for arg in action.in_arguments():
                arg_el = cls._action_argument_to_xml(arg)
                arg_list_el.append(arg_el)
            for arg in action.out_arguments():
                arg_el = cls._action_argument_to_xml(arg)
                arg_list_el.append(arg_el)

        return action_el

    @classmethod
    def _action_argument_to_xml(cls, argument: UpnpAction.Argument) -> ET.Element:
        """Convert action argument to service description XML."""
        arg_el = ET.Element("argument")
        ET.SubElement(arg_el, "name").text = argument.name
        ET.SubElement(arg_el, "direction").text = argument.direction
        ET.SubElement(
            arg_el, "relatedStateVariable"
        ).text = argument.related_state_variable.name
        return arg_el

    @classmethod
    def _state_variable_to_xml(cls, state_variable: UpnpStateVariable) -> ET.Element:
        """Convert state variable to service description XML."""
        state_var_el = ET.Element(
            "stateVariable", sendEvents="yes" if state_variable.send_events else "no"
        )
        ET.SubElement(state_var_el, "name").text = state_variable.name
        ET.SubElement(state_var_el, "dataType").text = state_variable.data_type

        if state_variable.allowed_values:
            value_list_el = ET.SubElement(state_var_el, "allowedValueList")
            for allowed_value in state_variable.allowed_values:
                ET.SubElement(value_list_el, "allowedValue").text = str(allowed_value)

        if not None in (state_variable.min_value, state_variable.max_value):
            value_range_el = ET.SubElement(state_var_el, "allowedValueRange")
            ET.SubElement(value_range_el, "minimum").text = str(
                state_variable.min_value
            )
            ET.SubElement(value_range_el, "maximum").text = str(
                state_variable.max_value
            )

        if state_variable.default_value is not None:
            ET.SubElement(state_var_el, "defaultValue").text = str(
                state_variable.default_value
            )

        return state_var_el


# UPnP Server based on https://gist.github.com/Consolatis/c7d9ecfe027c921d32a0176e66fce56a
# by @Consolatis


class NopRequester(UpnpRequester):  # pylint: disable=too-few-public-methods
    """NopRequester, does nothing."""


class UpnpServerAction(UpnpAction):
    """Representation of an Action."""

    async def async_handle(self, **kwargs: Any) -> Any:
        """Handle action."""
        self.validate_arguments(**kwargs)
        raise NotImplementedError()


class UpnpServerService(UpnpService):
    """UPnP Service representation."""

    SERVICE_DEFINITION: ServiceInfo
    STATE_VARIABLE_DEFINITIONS: Mapping[str, StateVariableTypeInfo]

    def __init__(self, requester: UpnpRequester) -> None:
        super().__init__(requester, self.SERVICE_DEFINITION, [], [])

        self._init_state_variables()
        self._init_actions()

    def _init_state_variables(self) -> None:
        """Initialize state variables from STATE_VARIABLE_DEFINITIONS."""
        for name, type_info in self.STATE_VARIABLE_DEFINITIONS.items():
            self.create_state_var(name, type_info)

    def create_state_var(
        self, name: str, type_info: StateVariableTypeInfo
    ) -> UpnpStateVariable:
        """Create UpnpStateVariable."""
        existing = self.state_variables.get(name, None)
        if existing is not None:
            raise UpnpError(f"StateVariable with the same name exists: {name}")

        state_var_info = StateVariableInfo(
            name,
            send_events=False,
            type_info=type_info,
            xml=ET.Element("stateVariable"),
        )
        # pylint: disable=protected-access
        state_var: UpnpStateVariable = UpnpStateVariable(
            state_var_info,
            UpnpFactory(self.requester)._state_variable_create_schema(type_info),
        )
        state_var.service = self
        if type_info.default_value is not None:
            state_var.upnp_value = type_info.default_value

        self.state_variables[state_var.name] = state_var
        return state_var

    def _init_actions(self) -> None:
        """Initialize actions from annotated methods."""
        for item in dir(self):
            if item in ("control_url", "event_sub_url", "scpd_url", "device"):
                continue

            thing = getattr(self, item, None)
            if not thing or not hasattr(thing, "__upnp_action__"):
                continue

            self._init_action(thing)

    def _init_action(self, func: Callable) -> UpnpAction:
        """Initialize action for method."""
        name, in_args, out_args = cast(
            Tuple[str, Mapping[str, str], Mapping[str, str]],
            getattr(func, "__upnp_action__"),
        )

        arg_infos: List[ActionArgumentInfo] = []
        args: List[UpnpAction.Argument] = []
        for arg_name, state_var_name in in_args.items():
            # Validate function has parameter.
            assert arg_name in func.__annotations__

            # Validate parameter type.
            annotation = func.__annotations__.get(arg_name, None)
            state_var = self.state_variable(state_var_name)
            assert state_var.data_type_mapping["type"] == annotation

            # Build in-argument.
            arg_info = ActionArgumentInfo(
                arg_name,
                direction="in",
                state_variable_name=state_var.name,
                xml=ET.Element("server_argument"),
            )
            arg_infos.append(arg_info)

            arg = UpnpAction.Argument(arg_info, state_var)
            args.append(arg)

        for arg_name, state_var_name in out_args.items():
            # Build out-argument.
            state_var = self.state_variable(state_var_name)
            arg_info = ActionArgumentInfo(
                arg_name,
                direction="out",
                state_variable_name=state_var.name,
                xml=ET.Element("server_argument"),
            )
            arg_infos.append(arg_info)

            arg = UpnpAction.Argument(arg_info, state_var)
            args.append(arg)

        action_info = ActionInfo(
            name=name,
            arguments=arg_infos,
            xml=ET.Element("server_action"),
        )
        action = UpnpServerAction(action_info, args)
        action.async_handle = func
        action.service = self
        self.actions[name] = action
        return action

    async def async_handle_action(self, action_name: str, **kwargs: Any) -> Any:
        """Handle action."""
        action = cast(UpnpServerAction, self.actions[action_name])
        action.validate_arguments(**kwargs)
        return await action.async_handle(**kwargs)


class UpnpServerDevice(UpnpDevice):
    """UPnP Device representation."""

    DEVICE_DEFINITION: DeviceInfo
    EMBEDDED_DEVICES: Sequence[Type["UpnpServerDevice"]]
    SERVICES: Sequence[Type[UpnpServerService]]

    def __init__(
        self,
        requester: UpnpRequester,
        base_uri: str,
    ) -> None:
        """Initialize."""
        services = [service_type(requester=requester) for service_type in self.SERVICES]
        embedded_devices = [
            device_type(requester=requester, base_uri=base_uri)
            for device_type in self.EMBEDDED_DEVICES
        ]
        super().__init__(
            requester=requester,
            device_info=self.DEVICE_DEFINITION,
            services=services,
            embedded_devices=embedded_devices,
        )
        self.base_uri = base_uri


def callable_action(
    name: str, in_args: Mapping[str, str], out_args: Mapping[str, str]
) -> Callable:
    """Declare method as a callable UpnpAction."""

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            return func(*args, **kwargs)

        setattr(wrapper, "__upnp_action__", [name, in_args, out_args])

        return wrapper

    return decorator


async def _parse_action_body(
    service: UpnpServerService, request: aiohttp.web.Request
) -> Tuple[str, Dict[str, Any]]:
    """Parse action body."""
    # Parse call.
    soap_action = request.headers.get("SOAPAction", "").strip('"')
    try:
        _, action_name = soap_action.split("#")
        data = await request.text()
        root_el: ET.Element = DET.fromstring(data)
        body_el = root_el.find("s:Body", NAMESPACES)
        assert body_el
        rpc_el = body_el[0]
    except Exception as exc:
        raise aiohttp.web.HTTPBadRequest(reason="InvalidSoap") from exc

    if action_name not in service.actions:
        raise aiohttp.web.HTTPBadRequest(reason="InvalidAction")

    kwargs: Dict[str, Any] = {}
    action = service.action(action_name)
    for arg in rpc_el:
        action_arg = action.argument(arg.tag, direction="in")
        if action_arg is None:
            raise aiohttp.web.HTTPBadRequest(reason="InvalidActionArgument")
        state_var = action_arg.related_state_variable
        kwargs[arg.tag] = state_var.coerce_python(arg.text or "")

    return action_name, kwargs


def _create_action_response(
    service: UpnpServerService, action_name: str, result: Dict[str, UpnpStateVariable]
) -> aiohttp.web.Response:
    """Create action call response."""
    envelope_el = ET.Element(
        "s:Envelope",
        attrib={
            "xmlns:s": NAMESPACES["s"],
            "s:encodingStyle": NAMESPACES["es"],
        },
    )
    body_el = ET.SubElement(envelope_el, "s:Body")

    response_el = ET.SubElement(
        body_el, f"st:{action_name}Response", attrib={"xmlns:st": service.service_type}
    )
    for key, value in result.items():
        ET.SubElement(response_el, key).text = value.upnp_value

    return aiohttp.web.Response(
        content_type="text/xml",
        charset="utf-8",
        body=ET.tostring(envelope_el, encoding="utf-8"),
    )


def _create_error_action_response(
    exception: UpnpError,
) -> aiohttp.web.Response:
    """Create action call response."""
    envelope_el = ET.Element(
        "s:Envelope",
        attrib={
            "xmlns:s": NAMESPACES["s"],
            "s:encodingStyle": NAMESPACES["es"],
        },
    )
    body_el = ET.SubElement(envelope_el, "s:Body")
    fault_el = ET.SubElement(body_el, "s:Fault")
    ET.SubElement(fault_el, "faultcode").text = "s:Client"
    ET.SubElement(fault_el, "faultstring").text = "UPnPError"
    detail_el = ET.SubElement(fault_el, "detail")
    error_el = ET.SubElement(
        detail_el, "UPnPError", xmlns="urn:schemas-upnp-org:control-1-0"
    )
    error_code = (
        exception.error_code or UpnpActionErrorCode.ACTION_FAILED.value
        if isinstance(exception, UpnpActionError)
        else 402
        if isinstance(exception, UpnpValueError)
        else 501
    )
    ET.SubElement(error_el, "errorCode").text = str(error_code)
    ET.SubElement(error_el, "errorDescription").text = "Action Failed"

    return aiohttp.web.Response(
        status=500,
        content_type="text/xml",
        charset="utf-8",
        body=ET.tostring(envelope_el, encoding="utf-8"),
    )


async def action_handler(
    service: UpnpServerService, request: aiohttp.web.Request
) -> aiohttp.web.Response:
    """Action handler."""
    action_name, kwargs = await _parse_action_body(service, request)

    # Do call.
    try:
        call_result = await service.async_handle_action(action_name, **kwargs)
    except UpnpValueError as exc:
        return _create_error_action_response(exc)
    except UpnpActionError as exc:
        return _create_error_action_response(exc)

    return _create_action_response(service, action_name, call_result)


async def subscribe_handler(
    _service: UpnpServerService, _request: aiohttp.web.Request
) -> aiohttp.web.Response:
    """SUBSCRIBE handler."""
    return aiohttp.web.Response(status=404)


async def to_xml(
    thing: Union[UpnpServerDevice, UpnpServerService], _request: aiohttp.web.Request
) -> aiohttp.web.Response:
    """Construct device/service description."""
    serializer = UpnpXmlSerializer()
    thing_el = serializer.to_xml(thing)
    encoding = "utf-8"
    thing_xml = ET.tostring(thing_el, encoding=encoding)
    return aiohttp.web.Response(
        content_type="text/xml", charset=encoding, body=thing_xml
    )


async def run_server(
    source: AddressTupleVXType, port: int, server_device: Type[UpnpServerDevice]
) -> None:
    """Run server."""
    # HTTP
    app = aiohttp.web.Application()

    requester = NopRequester()
    is_ipv6 = ":" in source[0]
    base_uri = (
        f"http://[{source[0]}]:{port}" if is_ipv6 else f"http://{source[0]}:{port}"
    )
    device = server_device(requester, base_uri)  # type: UpnpServerDevice

    # Set up routes.
    # Root device.
    app.router.add_get(device.device_url, partial(to_xml, device))

    # Services.
    for service in device.all_services:
        service = cast(UpnpServerService, service)
        app.router.add_get(
            service.SERVICE_DEFINITION.scpd_url, partial(to_xml, service)
        )
        app.router.add_post(
            service.SERVICE_DEFINITION.control_url, partial(action_handler, service)
        )
        app.router.add_route(
            "SUBSCRIBE",
            service.SERVICE_DEFINITION.event_sub_url,
            partial(subscribe_handler, service),
        )

    runner = aiohttp.web.AppRunner(app)
    await runner.setup()

    host = f"{source[0]}%{source[3]}" if is_ipv6 else source[0]
    site = aiohttp.web.TCPSite(runner, host, port)
    await site.start()

    LOGGER.info("Device at %s%s", device.base_uri, device.device_url)

    # SSDP
    target: AddressTupleVXType = (
        SSDP_TARGET_V6[:-1] + (source[3],) if is_ipv6 else SSDP_TARGET_V4
    )

    search_responder = SsdpSearchResponder(device, source, target)
    await search_responder.async_start()

    advertisement_announcer = SsdpAdvertisementAnnouncer(device, source, target)
    await advertisement_announcer.async_start()

    try:
        while True:
            await asyncio.sleep(3600)
    except KeyboardInterrupt:
        pass

    await advertisement_announcer.async_stop()
    await search_responder.async_stop()
