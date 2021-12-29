# -*- coding: utf-8 -*-
"""UPnP Server."""
import asyncio
import logging
import xml.etree.ElementTree as ET
from asyncio.transports import DatagramTransport
from functools import wraps
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Union, cast

import aiohttp.web as aiohttp_web
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
        if self._transport:
            self._transport.close()


# UPnP Server based on https://gist.github.com/Consolatis/c7d9ecfe027c921d32a0176e66fce56a
# by @Consolatis


class NopRequester(UpnpRequester):  # pylint: disable=too-few-public-methods
    """NopRequester, does nothing."""


# XML patching.


class UpnpServerAction(UpnpAction):
    """Representation of an Action."""

    async def async_handle(self, **kwargs: Any) -> Any:
        """Handle action."""
        self.validate_arguments(**kwargs)
        raise NotImplementedError()


# Usable frontends.


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


# Decorators.


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


# Utils.


async def action_handler(
    service: UpnpServerService, request: aiohttp_web.Request
) -> aiohttp_web.Response:
    """Action handler."""
    # pylint: disable=too-many-locals
    # Parse call.
    soap = request.headers.get("SOAPAction", "").strip('"')
    try:
        _, action_name = soap.split("#")
        data = await request.text()
        root_el: ET.Element = DET.fromstring(data)
        body_els: Sequence[ET.Element] = root_el.find("s:Body", NAMESPACES)
        rpc_el = body_els[0]
    except Exception as exc:
        raise aiohttp_web.HTTPBadRequest(reason="InvalidSoap") from exc

    if action_name not in service.actions:
        raise aiohttp_web.HTTPBadRequest(reason="InvalidAction")

    kwargs: Dict[str, Any] = {}
    action = service.action(action_name)
    for arg in rpc_el:
        _arg = action.argument(arg.tag, direction="in")
        if _arg is None:
            raise aiohttp_web.HTTPBadRequest(reason="InvalidArg")
        state_var = _arg.related_state_variable
        kwargs[arg.tag] = state_var.coerce_python(arg.text)

    # Do call.
    try:
        result = await service.async_handle_action(action_name, **kwargs)
    except UpnpValueError as exc:
        raise aiohttp_web.HTTPBadRequest(reason="InvalidArgFormat") from exc

    # Build response.
    rpc_el.tag += "Response"
    rpc_el.clear()  # Re-use part of request.
    for key in result:
        ET.SubElement(rpc_el, key).text = result[key].upnp_value

    return aiohttp_web.Response(
        content_type="text/xml",
        charset="utf-8",
        body=ET.tostring(root_el, encoding="utf-8"),
    )


async def subscribe_handler(service: UpnpServerService, request: aiohttp_web.Request
) -> aiohttp_web.Response:
    """SUBSCRIBE handler."""
    return aiohttp_web.Response(status=404)


async def to_xml(
    thing: Union[UpnpServerDevice, UpnpServerService], _request: aiohttp_web.Request
) -> aiohttp_web.Response:
    """Construct device/service description."""
    root_el = ET.Element("root", xmlns="urn:schemas-upnp-org:device-1-0")
    spec_version_el = ET.SubElement(root_el, "specVersion")
    ET.SubElement(spec_version_el, "major").text = "1"
    ET.SubElement(spec_version_el, "minor").text = "0"

    thing_el = thing.to_xml()
    root_el.append(thing_el)

    encoding = "utf-8"
    return aiohttp_web.Response(
        content_type="text/xml", charset=encoding, body=ET.tostring(root_el, encoding=encoding)
    )
