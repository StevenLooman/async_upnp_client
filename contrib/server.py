# -*- coding: utf-8 -*-
"""UPnP Server."""
import asyncio
import logging
import xml.etree.ElementTree as ET
from asyncio.transports import DatagramTransport
from functools import partial, wraps
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple, Union, cast

import aiohttp.web
import defusedxml.ElementTree as DET  # pylint: disable=import-error

from async_upnp_client import ssdp
from async_upnp_client import net
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
    DeviceInfo,
    ServiceInfo,
    StateVariableInfo,
    StateVariableTypeInfo,
)
from async_upnp_client.exceptions import UpnpValueError

NAMESPACES = {"s": "http://schemas.xmlsoap.org/soap/envelope/"}
LOGGER = logging.getLogger("async_upnp_client.server")


class SsdpSearchResponder:
    """SSDP SEARCH responder."""

    def __init__(
        self,
        device: "UpnpServerDevice",
        source: Union[ssdp.AddressTupleVXType, ssdp.IPvXAddress, None] = None,
        target: Union[ssdp.AddressTupleVXType, ssdp.IPvXAddress, None] = None,
    ) -> None:
        """Init the ssdp search responder class."""
        self.device = device
        self.target = ssdp.get_target_address_tuple(target, source=source)
        self.source = net.get_source_address_tuple(self.target, source)
        self._transport: Optional[DatagramTransport] = None

    async def _async_on_connect(self, transport: DatagramTransport) -> None:
        """Handle on connect."""
        self._transport = transport

    async def _async_on_data(
        self,
        request_line: str,
        headers: ssdp.SsdpHeaders,
        addr: ssdp.AddressTupleVXType,
    ) -> None:
        """Handle data."""
        assert self._transport

        if (
            request_line != "M-SEARCH * HTTP/1.1"
            or headers.get("MAN") != ssdp.SSDP_DISCOVER
        ):
            return

        LOGGER.debug("Received M-SEARCH from: %s, headers: %s", addr, headers)

        protocol = cast(ssdp.SsdpProtocol, self._transport.get_protocol())
        response_line = "HTTP/1.1 200 OK"
        response_headers = {
            "Cache-Control": "max-age=1800",
            "Server": "async-upnp-client/1.0 UPnP/1.0 Dummy_tv/1.0",
            "ST": f"{self.device.device_type}",
            "USN": f"{self.device.udn}::{self.device.device_type}",
            "EXT": "",
            "LOCATION": f"{self.device.base_uri}{self.device.device_url}",
        }
        packet = ssdp.build_ssdp_packet(response_line, response_headers)
        protocol.send_ssdp_packet(packet, addr)

        # XXX TODO: 3n + 2k + 1?
        # 1 per device
        # 1 per service
        # ???

    async def async_start(self) -> None:
        """Start."""
        LOGGER.debug("Start listening for advertisements")

        # Construct a socket for use with this pairs of endpoints.
        sock, _, sock_target = ssdp.get_ssdp_socket(self.source, self.target)
        LOGGER.debug("Binding to address: %s", sock_target)
        sock.bind(sock_target)

        # Create protocol and send discovery packet.
        loop = asyncio.get_event_loop()
        await loop.create_datagram_endpoint(
            lambda: ssdp.SsdpProtocol(
                loop,
                on_connect=self._async_on_connect,
                on_data=self._async_on_data,
            ),
            sock=sock,
        )

    async def async_stop(self) -> None:
        """Stop listening for advertisements."""
        LOGGER.debug("Stop listening for advertisements")

        LOGGER.debug("Announcing ssdp:byebye")
        self._transport.close()
        raise NotImplementedError()


class UpnpXmlSerializer:
    """Helper class to create device/service description from UpnpDevice/UpnpService."""

    @classmethod
    def to_xml(cls, thing: Union[UpnpDevice, UpnpService]) -> ET.Element:
        """Convert thing to XML."""
        if isinstance(thing, UpnpDevice):
            return cls._device_to_xml(thing)
        elif isinstance(thing, UpnpService):
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
            ET.SubElement(icon_el, "width").text = icon.width
            ET.SubElement(icon_el, "height").text = icon.height
            ET.SubElement(icon_el, "depth").text = icon.depth
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
        for device in device.embedded_devices.values():
            child_device_el = cls._device_to_xml_bare(device)
            device_list_el.append(child_device_el)

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
            ET.SubElement(value_range_el, "minimum").text = str(state_variable.min_value)
            ET.SubElement(value_range_el, "maximum").text = str(state_variable.max_value)

        if state_variable.default_value is not None:
            ET.SubElement(state_var_el, "defaultValue").text = str(state_variable.default_value)

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
        state_var = UpnpStateVariable(
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
        name, in_args, out_args = func.__upnp_action__

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
            arg = UpnpAction.Argument(arg_info, state_var)
            args.append(arg)

        action_info = ActionInfo(
            name=name, arguments=args, xml=ET.Element("server_action")
        )
        action = UpnpAction(action_info, args)
        action.async_handle = func
        action.service = self
        self.actions[name] = action
        return action

    async def async_handle_action(self, action_name: str, **kwargs: Any) -> Any:
        """Handle action."""
        action = self.actions[action_name]  # type: UpnpAction
        action.validate_arguments(**kwargs)
        return await action.async_handle(**kwargs)


class UpnpServerDevice(UpnpDevice):
    """UPnP Device representation."""

    DEVICE_DEFINITION: DeviceInfo

    def __init__(
        self,
        requester: UpnpRequester,
        services: Sequence[UpnpService],
        embedded_devices: Sequence[UpnpDevice],
        base_uri: str,
    ) -> None:
        """Initialize."""
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

        wrapper.__upnp_action__ = [name, in_args, out_args]

        return wrapper

    return decorator


async def _parse_action_body(service: UpnpServerService, request: aiohttp.web.Request) -> Tuple[str, Dict[str, Any]]:
    """Parse action body."""
    # Parse call.
    soap = request.headers.get("SOAPAction", "").strip('"')
    try:
        _, action_name = soap.split("#")
        data = await request.text()
        root_el: ET.Element = DET.fromstring(data)
        body_els: Sequence[ET.Element] = root_el.find("s:Body", NAMESPACES)
        rpc_el = body_els[0]
    except Exception as exc:
        raise aiohttp.web.HTTPBadRequest(reason="InvalidSoap") from exc

    if action_name not in service.actions:
        raise aiohttp.web.HTTPBadRequest(reason="InvalidAction")

    kwargs: Dict[str, Any] = {}
    action = service.action(action_name)
    for arg in rpc_el:
        action_arg = action.argument(arg.tag, direction="in")
        if action_arg is None:
            raise aiohttp.web.HTTPBadRequest(reason="InvalidArg")
        state_var = action_arg.related_state_variable
        kwargs[arg.tag] = state_var.coerce_python(arg.text)

    return action_name, kwargs


def _create_action_response(service: UpnpServerService, action_name: str, result: Dict[str, UpnpStateVariable]) -> aiohttp.web.Response:
    """Create action call response."""
    ns_soap = "http://schemas.xmlsoap.org/soap/envelope/"
    envelope_el = ET.Element("s:Envelope", attrib={
        "xmlns:s": ns_soap,
        "s:encodingStyle": "http://schemas.xmlsoap.org/soap/encoding/",
    })
    body_el = ET.SubElement(envelope_el, "s:Body")

    response_el = ET.SubElement(body_el, f"st:{action_name}Response", attrib={"xmlns:st": service.service_type})
    for key, value in result.items():
        ET.SubElement(response_el, key).text = value.upnp_value

    return aiohttp.web.Response(
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
        raise aiohttp.web.HTTPBadRequest(reason="InvalidArgFormat") from exc

    return _create_action_response(service, action_name, call_result)


async def subscribe_handler(service: UpnpServerService, request: aiohttp.web.Request
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
    return aiohttp.web.Response(content_type="text/xml", charset=encoding, body=thing_xml)


async def run_server(source: tuple, port: int, server_device: UpnpServerDevice) -> None:
    """Run server."""
    # HTTP
    app = aiohttp.web.Application()

    requester = NopRequester()
    is_ipv6 = ":" in source[0]
    base_uri = (
        f"http://[{source[0]}]:{port}"
        if is_ipv6
        else f"http://{source[0]}:{port}"
    )
    device = server_device(requester, base_uri)  # type: UpnpServerDevice

    # Set up routes.
    # Root device.
    app.router.add_get(device.device_url, partial(to_xml, device))

    # Services.
    for service in device.all_services:
        service = cast(UpnpServerService, service)
        app.router.add_get(service.SERVICE_DEFINITION.scpd_url, partial(to_xml, service))
        app.router.add_post(
            service.SERVICE_DEFINITION.control_url, partial(action_handler, service)
        )
        app.router.add_route("SUBSCRIBE", service.SERVICE_DEFINITION.event_sub_url, partial(subscribe_handler, service))

    runner = aiohttp.web.AppRunner(app)
    await runner.setup()

    host = f"{source[0]}%{source[3]}" if is_ipv6 else source[0]
    site = aiohttp.web.TCPSite(runner, host, port)
    await site.start()

    LOGGER.info("Device at %s%s", device.base_uri, device.device_url)

    # SSDP
    search_responder = SsdpSearchResponder(device, source)
    await search_responder.async_start()

    try:
        await asyncio.sleep(3600)
    except KeyboardInterrupt:
        pass

    await search_responder.async_stop()
