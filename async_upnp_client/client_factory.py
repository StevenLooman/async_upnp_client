# -*- coding: utf-8 -*-
"""UPnP factory module."""

import logging
import urllib.parse
from typing import Any, Dict, List, Optional, Sequence  # noqa: F401
from xml.etree import ElementTree as ET

import defusedxml.ElementTree as DET  # type: ignore
import voluptuous as vol  # type: ignore

from async_upnp_client.client import UpnpAction
from async_upnp_client.client import UpnpDevice
from async_upnp_client.client import UpnpError
from async_upnp_client.client import UpnpRequester
from async_upnp_client.client import UpnpService
from async_upnp_client.client import UpnpStateVariable
from async_upnp_client.const import NS
from async_upnp_client.const import STATE_VARIABLE_TYPE_MAPPING
from async_upnp_client.const import DeviceInfo
from async_upnp_client.const import ServiceInfo
from async_upnp_client.const import ActionArgumentInfo
from async_upnp_client.const import ActionInfo
from async_upnp_client.const import StateVariableInfo
from async_upnp_client.const import StateVariableTypeInfo


_LOGGER = logging.getLogger(__name__)


class UpnpFactory:
    """
    Factory for UpnpService and friends.

    Use UpnpFactory.async_create_services() to instantiate UpnpServices from a device XML.
    You have probably received this URL from netdisco, for example.
    """

    def __init__(self,
                 requester: UpnpRequester,
                 disable_state_variable_validation: bool = False) -> None:
        """Initializer."""
        self.requester = requester
        self._properties = {
            'disable_state_variable_validation': disable_state_variable_validation,
        }

    async def async_create_device(self, description_url: str) -> UpnpDevice:
        """Create a UpnpDevice, with all of it UpnpServices."""
        root = await self._async_get_url_xml(description_url)

        # get device info
        device_desc = self._device_parse_xml(root, description_url)

        # get services
        services = []
        for service_desc_xml in root.findall('.//device:serviceList/device:service', NS):
            service = await self.async_create_service(service_desc_xml, description_url)
            services.append(service)

        return UpnpDevice(self.requester, device_desc, services)

    def _device_parse_xml(self, device_description_xml: ET.Element, description_url: str) \
            -> DeviceInfo:
        """Parse device description XML."""
        # pylint: disable=no-self-use
        desc_xml = device_description_xml
        return DeviceInfo(
            device_type=desc_xml.findtext('.//device:deviceType', '', NS),
            friendly_name=desc_xml.findtext('.//device:friendlyName', '', NS),
            manufacturer=desc_xml.findtext('.//device:manufacturer', '', NS),
            model_name=desc_xml.findtext('.//device:modelName', '', NS),
            udn=desc_xml.findtext('.//device:UDN', '', NS),
            model_description=desc_xml.findtext('.//device:modelDescription', None, NS),
            model_number=desc_xml.findtext('.//device:modelNumber', None, NS),
            url=description_url,
            xml=desc_xml)

    async def async_create_service(self,
                                   service_description_xml: ET.Element,
                                   base_url: str) -> UpnpService:
        """Retrieve the SCPD for a service and create a UpnpService from it."""
        scpd_url = service_description_xml.findtext('device:SCPDURL', None, NS)
        scpd_url = urllib.parse.urljoin(base_url, scpd_url)
        scpd_xml = await self._async_get_url_xml(scpd_url)
        return self.create_service(service_description_xml, scpd_xml)

    def create_service(self,
                       service_description_xml: ET.Element,
                       scpd_xml: ET.Element) -> UpnpService:
        """Create a UnpnpService, with UpnpActions and UpnpStateVariables from scpd_xml."""
        service_description = self._service_parse_xml(service_description_xml)
        state_vars = self.create_state_variables(scpd_xml)
        actions = self.create_actions(scpd_xml, state_vars)
        return UpnpService(self.requester, service_description, state_vars, actions)

    def _service_parse_xml(self, service_description_xml: ET.Element) -> ServiceInfo:
        """Parse service description XML."""
        # pylint: disable=no-self-use
        desc_xml = service_description_xml
        return ServiceInfo(
            service_id=desc_xml.findtext('device:serviceId', '', NS),
            service_type=desc_xml.findtext('device:serviceType', '', NS),
            control_url=desc_xml.findtext('device:controlURL', '', NS),
            event_sub_url=desc_xml.findtext('device:eventSubURL', '', NS),
            scpd_url=desc_xml.findtext('device:SCPDURL', '', NS),
            xml=desc_xml)

    def create_state_variables(self, scpd_xml: ET.Element) -> List[UpnpStateVariable]:
        """Create UpnpStateVariables from scpd_xml."""
        state_vars = []
        for state_var_xml in scpd_xml.findall('.//service:stateVariable', NS):
            state_var = self.create_state_variable(state_var_xml)
            state_vars.append(state_var)
        return state_vars

    def create_state_variable(self, state_variable_xml: ET.Element) -> UpnpStateVariable:
        """Create UpnpStateVariable from state_variable_xml."""
        state_variable_info = self._state_variable_parse_xml(state_variable_xml)
        type_info = state_variable_info.type_info
        schema = self._state_variable_create_schema(type_info)
        return UpnpStateVariable(state_variable_info, schema)

    def _state_variable_parse_xml(self, state_variable_xml: ET.Element) -> StateVariableInfo:
        """Parse XML for state variable."""
        # pylint: disable=no-self-use

        # send events
        send_events = False
        if 'sendEvents' in state_variable_xml.attrib:
            send_events = state_variable_xml.attrib['sendEvents'] == 'yes'
        elif state_variable_xml.find('service:sendEventsAttribute', NS) is not None:
            send_events = \
                state_variable_xml.findtext('service:sendEventsAttribute', None, NS) == 'yes'
        else:
            _LOGGER.debug('Invalid XML for state variable/send events:\n%s',
                          ET.tostring(state_variable_xml, encoding='unicode'))

        # data type
        data_type = state_variable_xml.findtext('service:dataType', None, NS)
        if data_type not in STATE_VARIABLE_TYPE_MAPPING:
            raise UpnpError('Unsupported data type: %s' % (data_type, ))
        data_type = data_type
        data_type_python = STATE_VARIABLE_TYPE_MAPPING[data_type]

        # default value
        default_value = state_variable_xml.findtext('service:defaultValue', None, NS)

        # allowed value ranges
        allowed_value_range = {}  # type: Dict[str, Optional[str]]
        allowed_value_range_el = state_variable_xml.find('service:allowedValueRange', NS)
        if allowed_value_range_el is not None:
            allowed_value_range = {
                'min': allowed_value_range_el.findtext('service:minimum', None, NS),
                'max': allowed_value_range_el.findtext('service:maximum', None, NS),
                'step': allowed_value_range_el.findtext('service:step', None, NS),
            }

        # allowed value list
        allowed_values = None  # type: Optional[List[str]]
        allowed_value_list_el = state_variable_xml.find('service:allowedValueList', NS)
        if allowed_value_list_el is not None:
            allowed_values = \
                [v.text for v in allowed_value_list_el.findall('service:allowedValue', NS)
                 if v.text is not None]

        type_info = StateVariableTypeInfo(data_type=data_type,
                                          data_type_python=data_type_python,
                                          default_value=default_value,
                                          allowed_value_range=allowed_value_range,
                                          allowed_values=allowed_values,
                                          xml=state_variable_xml)
        name = state_variable_xml.findtext('service:name', '', NS).strip()
        return StateVariableInfo(name=name,
                                 send_events=send_events,
                                 type_info=type_info,
                                 xml=state_variable_xml)

    def _state_variable_create_schema(self, type_info: StateVariableTypeInfo) -> vol.Schema:
        """Create schema."""
        # construct validators
        # pylint: disable=no-self-use
        validators = []

        data_type_upnp = type_info.data_type
        data_type = STATE_VARIABLE_TYPE_MAPPING[data_type_upnp]
        validators.append(data_type)

        if not self._properties['disable_state_variable_validation']:
            if type_info.allowed_values:
                allowed_values = [data_type(allowed_value)
                                  for allowed_value in type_info.allowed_values]
                in_ = vol.In(allowed_values)
                validators.append(in_)

            if type_info.allowed_value_range:
                min_ = type_info.allowed_value_range.get('min', None)
                max_ = type_info.allowed_value_range.get('max', None)
                min_ = data_type(min_) if min_ else None
                max_ = data_type(max_) if max_ else None
                if min_ is not None or max_ is not None:
                    range_ = vol.Range(min=min_, max=max_)
                    validators.append(range_)

        # construct key
        key = vol.Required('value')

        if type_info.default_value is not None:
            default_value = type_info.default_value  # type: Any
            if data_type == bool:
                default_value = default_value == '1'
            else:
                default_value = data_type(default_value)
            key.default = default_value

        return vol.Schema({key: vol.All(*validators)})

    def create_actions(self, scpd_xml: ET.Element, state_variables: Sequence[UpnpStateVariable]) \
            -> List[UpnpAction]:
        """Create UpnpActions from scpd_xml."""
        actions = []
        for action_xml in scpd_xml.findall('.//service:action', NS):
            action = self.create_action(action_xml, state_variables)
            actions.append(action)
        return actions

    def create_action(self, action_xml: ET.Element, state_variables: Sequence[UpnpStateVariable]) \
            -> UpnpAction:
        """Create a UpnpAction from action_xml."""
        action_info = self._action_parse_xml(action_xml)
        svs = {sv.name: sv for sv in state_variables}
        arguments = [UpnpAction.Argument(arg_info, svs[arg_info.state_variable_name])
                     for arg_info in action_info.arguments]
        return UpnpAction(action_info, arguments)

    def _action_parse_xml(self, action_xml: ET.Element) -> ActionInfo:
        """Parse XML for action."""
        # pylint: disable=no-self-use

        # build arguments
        args = []  # type: List[ActionArgumentInfo]
        for argument_xml in action_xml.findall('.//service:argument', NS):
            argument_name = argument_xml.findtext('service:name', None, NS)
            if argument_name is None:
                _LOGGER.debug('Caught Action Argument without a name, ignoring')
                continue

            direction = argument_xml.findtext('service:direction', None, NS)
            if direction is None:
                _LOGGER.debug('Caught Action Argument without a direction, ignoring')
                continue

            state_variable_name = argument_xml.findtext('service:relatedStateVariable', None, NS)
            if state_variable_name is None:
                _LOGGER.debug('Caught Action Argument without a State Variable name, ignoring')
                continue

            argument_info = ActionArgumentInfo(
                name=argument_name,
                direction=direction,
                state_variable_name=state_variable_name,
                xml=argument_xml)
            args.append(argument_info)

        action_name = action_xml.findtext('service:name', None, NS)
        if action_name is None:
            _LOGGER.debug('Caught Action without a name, using default "nameless"')
            action_name = 'nameless'

        return ActionInfo(name=action_name,
                          arguments=args,
                          xml=action_xml)

    async def _async_get_url_xml(self, url: str) -> ET.Element:
        """Fetch device description."""
        status_code, _, response_body = \
            await self.requester.async_http_request('GET', url)

        if status_code != 200:
            raise UpnpError("Received status code: {}".format(status_code))

        root = DET.fromstring(response_body)  # type: ET.Element
        return root
