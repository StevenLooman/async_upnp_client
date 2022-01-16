# -*- coding: utf-8 -*-
"""UPnP factory module."""

import logging
import urllib.parse
from typing import Any, Dict, List, Optional, Sequence
from xml.etree import ElementTree as ET

import defusedxml.ElementTree as DET
import voluptuous as vol

from async_upnp_client.client import (
    UpnpAction,
    UpnpDevice,
    UpnpError,
    UpnpRequester,
    UpnpService,
    UpnpStateVariable,
)
from async_upnp_client.const import (
    NS,
    STATE_VARIABLE_TYPE_MAPPING,
    ActionArgumentInfo,
    ActionInfo,
    DeviceIcon,
    DeviceInfo,
    ServiceInfo,
    StateVariableInfo,
    StateVariableTypeInfo,
)
from async_upnp_client.exceptions import (
    UpnpResponseError,
    UpnpXmlContentError,
    UpnpXmlParseError,
)
from async_upnp_client.utils import absolute_url

_LOGGER = logging.getLogger(__name__)


class UpnpFactory:
    """
    Factory for UpnpService and friends.

    Use UpnpFactory.async_create_device() to instantiate UpnpDevice from a device XML.
    You have probably received this URL from netdisco, for example.
    """

    # pylint: disable=too-few-public-methods

    def __init__(
        self,
        requester: UpnpRequester,
        disable_state_variable_validation: bool = False,
        disable_unknown_out_argument_error: bool = False,
        non_strict: bool = False,
    ) -> None:
        """Initialize."""
        self.requester = requester
        self._non_strict = (
            non_strict
            or disable_unknown_out_argument_error
            or disable_state_variable_validation
        )

    async def async_create_device(
        self,
        description_url: str,
    ) -> UpnpDevice:
        """Create a UpnpDevice, with all of it UpnpServices."""
        _LOGGER.debug("Creating device, description_url: %s", description_url)
        root_el = await self._async_get(description_url)

        # get root device
        device_el = root_el.find("./device:device", NS)
        if device_el is None:
            raise UpnpXmlContentError("Could not find device element")

        return await self._async_create_device(device_el, description_url)

    async def _async_create_device(
        self, device_el: ET.Element, description_url: str
    ) -> UpnpDevice:
        """Create a device."""
        device_info = self._parse_device_el(device_el, description_url)

        # get services
        services = []
        for service_desc_el in device_el.findall(
            "./device:serviceList/device:service", NS
        ):
            service = await self._async_create_service(service_desc_el, description_url)
            services.append(service)

        embedded_devices = []
        for embedded_device_el in device_el.findall(
            "./device:deviceList/device:device", NS
        ):
            embedded_device = await self._async_create_device(
                embedded_device_el, description_url
            )
            embedded_devices.append(embedded_device)

        return UpnpDevice(self.requester, device_info, services, embedded_devices)

    def _parse_device_el(
        self, device_desc_el: ET.Element, description_url: str
    ) -> DeviceInfo:
        """Parse device description XML."""
        # pylint: disable=no-self-use
        icons = []
        for icon_el in device_desc_el.iterfind("./device:iconList/device:icon", NS):
            icon_url = icon_el.findtext("./device:url", "", NS)
            icon_url = absolute_url(description_url, icon_url)
            icon = DeviceIcon(
                mimetype=icon_el.findtext("./device:mimetype", "", NS),
                width=int(icon_el.findtext("./device:width", 0, NS)),
                height=int(icon_el.findtext("./device:height", 0, NS)),
                depth=int(icon_el.findtext("./device:depth", 0, NS)),
                url=icon_url,
            )
            icons.append(icon)

        return DeviceInfo(
            device_type=device_desc_el.findtext("./device:deviceType", "", NS),
            friendly_name=device_desc_el.findtext("./device:friendlyName", "", NS),
            manufacturer=device_desc_el.findtext("./device:manufacturer", "", NS),
            model_name=device_desc_el.findtext("./device:modelName", "", NS),
            udn=device_desc_el.findtext("./device:UDN", "", NS),
            model_description=device_desc_el.findtext(
                "./device:modelDescription", None, NS
            ),
            model_number=device_desc_el.findtext("./device:modelNumber", None, NS),
            serial_number=device_desc_el.findtext("./device:serialNumber", None, NS),
            url=description_url,
            icons=icons,
            xml=device_desc_el,
        )

    async def _async_create_service(
        self, service_description_el: ET.Element, base_url: str
    ) -> UpnpService:
        """Retrieve the SCPD for a service and create a UpnpService from it."""
        scpd_url = service_description_el.findtext("device:SCPDURL", None, NS)
        scpd_url = urllib.parse.urljoin(base_url, scpd_url)
        scpd_el = await self._async_get(scpd_url)

        if not self._non_strict and scpd_el.tag != f"{{{NS['service']}}}scpd":
            raise UpnpXmlContentError(f"Invalid document root: {scpd_el.tag}")

        service_info = self._parse_service_el(service_description_el)
        state_vars = self._create_state_variables(scpd_el)
        actions = self._create_actions(scpd_el, state_vars)
        return UpnpService(self.requester, service_info, state_vars, actions)

    def _parse_service_el(self, service_description_el: ET.Element) -> ServiceInfo:
        """Parse service description XML."""
        # pylint: disable=no-self-use
        return ServiceInfo(
            service_id=service_description_el.findtext("device:serviceId", "", NS),
            service_type=service_description_el.findtext("device:serviceType", "", NS),
            control_url=service_description_el.findtext("device:controlURL", "", NS),
            event_sub_url=service_description_el.findtext("device:eventSubURL", "", NS),
            scpd_url=service_description_el.findtext("device:SCPDURL", "", NS),
            xml=service_description_el,
        )

    def _create_state_variables(self, scpd_el: ET.Element) -> List[UpnpStateVariable]:
        """Create UpnpStateVariables from scpd_el."""
        service_state_table_el = scpd_el.find("./service:serviceStateTable", NS)
        if service_state_table_el is None:
            if self._non_strict:
                _LOGGER.debug("Could not find service state table element")
                return []
            raise UpnpXmlContentError("Could not find service state table element")

        state_vars = []
        for state_var_el in service_state_table_el.findall(
            "./service:stateVariable", NS
        ):
            state_var = self._create_state_variable(state_var_el)
            state_vars.append(state_var)
        return state_vars

    def _create_state_variable(
        self, state_variable_el: ET.Element
    ) -> UpnpStateVariable:
        """Create UpnpStateVariable from state_variable_el."""
        state_variable_info = self._parse_state_variable_el(state_variable_el)
        type_info = state_variable_info.type_info
        schema = self._state_variable_create_schema(type_info)
        return UpnpStateVariable(state_variable_info, schema)

    def _parse_state_variable_el(
        self, state_variable_el: ET.Element
    ) -> StateVariableInfo:
        """Parse XML for state variable."""
        # pylint: disable=no-self-use

        # send events
        send_events = False
        if "sendEvents" in state_variable_el.attrib:
            send_events = state_variable_el.attrib["sendEvents"] == "yes"
        elif state_variable_el.find("service:sendEventsAttribute", NS) is not None:
            send_events = (
                state_variable_el.findtext("service:sendEventsAttribute", None, NS)
                == "yes"
            )
        else:
            _LOGGER.debug(
                "Invalid XML for state variable/send events: %s",
                ET.tostring(state_variable_el, encoding="unicode"),
            )

        # data type
        data_type = state_variable_el.findtext("service:dataType", None, NS)
        if data_type is None or data_type not in STATE_VARIABLE_TYPE_MAPPING:
            raise UpnpError(f"Unsupported data type: {data_type}")

        data_type_mapping = STATE_VARIABLE_TYPE_MAPPING[data_type]

        # default value
        default_value = state_variable_el.findtext("service:defaultValue", None, NS)

        # allowed value ranges
        allowed_value_range: Dict[str, Optional[str]] = {}
        allowed_value_range_el = state_variable_el.find("service:allowedValueRange", NS)
        if allowed_value_range_el is not None:
            allowed_value_range = {
                "min": allowed_value_range_el.findtext("service:minimum", None, NS),
                "max": allowed_value_range_el.findtext("service:maximum", None, NS),
                "step": allowed_value_range_el.findtext("service:step", None, NS),
            }

        # allowed value list
        allowed_values: Optional[List[str]] = None
        allowed_value_list_el = state_variable_el.find("service:allowedValueList", NS)
        if allowed_value_list_el is not None:
            allowed_values = [
                v.text
                for v in allowed_value_list_el.findall("service:allowedValue", NS)
                if v.text is not None
            ]

        type_info = StateVariableTypeInfo(
            data_type=data_type,
            data_type_mapping=data_type_mapping,
            default_value=default_value,
            allowed_value_range=allowed_value_range,
            allowed_values=allowed_values,
            xml=state_variable_el,
        )
        name = state_variable_el.findtext("service:name", "", NS).strip()
        return StateVariableInfo(
            name=name,
            send_events=send_events,
            type_info=type_info,
            xml=state_variable_el,
        )

    def _state_variable_create_schema(
        self, type_info: StateVariableTypeInfo
    ) -> vol.Schema:
        """Create schema."""
        # construct validators
        validators = []

        data_type_upnp = type_info.data_type
        data_type_mapping = STATE_VARIABLE_TYPE_MAPPING[data_type_upnp]
        data_type = data_type_mapping["type"]
        validators.append(data_type)

        data_type_validator = data_type_mapping.get("validator")
        if data_type_validator:
            validators.append(data_type_validator)

        if not self._non_strict:
            in_coercer = data_type_mapping["in"]
            if type_info.allowed_values:
                allowed_values = [
                    in_coercer(allowed_value)
                    for allowed_value in type_info.allowed_values
                ]
                in_ = vol.In(allowed_values)
                validators.append(in_)

            if type_info.allowed_value_range:
                min_ = type_info.allowed_value_range.get("min", None)
                max_ = type_info.allowed_value_range.get("max", None)
                min_ = in_coercer(min_) if min_ else None
                max_ = in_coercer(max_) if max_ else None
                if min_ is not None or max_ is not None:
                    range_ = vol.Range(min=min_, max=max_)
                    validators.append(range_)

        # construct key
        key = vol.Required("value")

        if type_info.default_value is not None and type_info.default_value != "":
            default_value: Any = type_info.default_value
            if data_type == bool:
                default_value = default_value == "1"
            else:
                default_value = data_type(default_value)
            key.default = default_value

        return vol.Schema(vol.All(*validators))

    def _create_actions(
        self, scpd_el: ET.Element, state_variables: Sequence[UpnpStateVariable]
    ) -> List[UpnpAction]:
        """Create UpnpActions from scpd_el."""
        action_list_el = scpd_el.find("./service:actionList", NS)
        if action_list_el is None:
            return []

        actions = []
        for action_el in action_list_el.findall("./service:action", NS):
            action = self._create_action(action_el, state_variables)
            actions.append(action)
        return actions

    def _create_action(
        self, action_el: ET.Element, state_variables: Sequence[UpnpStateVariable]
    ) -> UpnpAction:
        """Create a UpnpAction from action_el."""
        action_info = self._parse_action_el(action_el)
        svs = {sv.name: sv for sv in state_variables}
        arguments = [
            UpnpAction.Argument(arg_info, svs[arg_info.state_variable_name])
            for arg_info in action_info.arguments
        ]
        return UpnpAction(action_info, arguments, non_strict=self._non_strict)

    def _parse_action_el(self, action_el: ET.Element) -> ActionInfo:
        """Parse XML for action."""
        # pylint: disable=no-self-use

        # build arguments
        args: List[ActionArgumentInfo] = []
        for argument_el in action_el.findall(
            "./service:argumentList/service:argument", NS
        ):
            argument_name = argument_el.findtext("service:name", None, NS)
            if argument_name is None:
                _LOGGER.debug("Caught Action Argument without a name, ignoring")
                continue

            direction = argument_el.findtext("service:direction", None, NS)
            if direction is None:
                _LOGGER.debug("Caught Action Argument without a direction, ignoring")
                continue

            state_variable_name = argument_el.findtext(
                "service:relatedStateVariable", None, NS
            )
            if state_variable_name is None:
                _LOGGER.debug(
                    "Caught Action Argument without a State Variable name, ignoring"
                )
                continue

            argument_info = ActionArgumentInfo(
                name=argument_name,
                direction=direction,
                state_variable_name=state_variable_name,
                xml=argument_el,
            )
            args.append(argument_info)

        action_name = action_el.findtext("service:name", None, NS)
        if action_name is None:
            _LOGGER.debug('Caught Action without a name, using default "nameless"')
            action_name = "nameless"

        return ActionInfo(name=action_name, arguments=args, xml=action_el)

    async def _async_get(self, url: str) -> ET.Element:
        """Get a url."""
        (
            status_code,
            response_headers,
            response_body,
        ) = await self.requester.async_http_request("GET", url)

        if status_code != 200:
            raise UpnpResponseError(status=status_code, headers=response_headers)

        description: str = (response_body or "").rstrip(" \t\r\n\0")
        try:
            element: ET.Element = DET.fromstring(description)
            return element
        except ET.ParseError as err:
            _LOGGER.debug("Unable to parse XML: %s\nXML:\n%s", err, description)
            raise UpnpXmlParseError(err) from err
