# -*- coding: utf-8 -*-
"""UPnP client module."""

import abc
import asyncio
import logging
import urllib.parse
from datetime import datetime
from datetime import timezone
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape, unescape

import voluptuous as vol


NS = {
    'soap_envelope': 'http://schemas.xmlsoap.org/soap/envelope/',

    'device': 'urn:schemas-upnp-org:device-1-0',
    'service': 'urn:schemas-upnp-org:service-1-0',
    'event': 'urn:schemas-upnp-org:event-1-0',
    'control': 'urn:schemas-upnp-org:control-1-0',
}


_LOGGER = logging.getLogger(__name__)
_LOGGER_TRAFFIC = logging.getLogger(__name__ + ".traffic")


class UpnpRequester(object):
    """Abstract base class used for performing async HTTP requests."""

    @asyncio.coroutine
    @abc.abstractmethod
    def async_http_request(self, method, url, headers=None, body=None):
        """Do a HTTP request."""
        pass


class UpnpError(Exception):
    """UpnpError."""


class UpnpDevice(object):
    """UPnP Device representation."""

    def __init__(self, requester, device_url, device_description, services):
        self._requester = requester
        self._device_url = device_url
        self._device_description = device_description
        self._services = {service.service_type: service for service in services}

        for service in services:
            service.device = self

    @property
    def name(self):
        """Get the name of this device."""
        return self._device_description['friendly_name']

    def service(self, service_type):
        """Get service by service_type."""
        return self._services.get(service_type)

    @property
    def services(self):
        """Get all services."""
        return self._services

    @property
    def device_url(self):
        """Get device url."""
        return self._device_url

    @asyncio.coroutine
    def async_ping(self):
        """Ping the device"""
        yield from self._requester.async_http_request('GET', self._device_url)


class UpnpService(object):
    """UPnP Service representation."""

    def __init__(self, requester, service_description, state_variables, actions):
        self._requester = requester
        self._service_description = service_description
        self._state_variables = {sv.name: sv for sv in state_variables}
        self._actions = {ac.name: ac for ac in actions}

        self._subscription_sid = None
        self._on_state_variable_change = None
        self._device = None

        for state_var in state_variables:
            state_var.service = self
        for action in actions:
            action.service = self

    @property
    def device(self):
        """Get parent UpnpDevice."""
        return self._device

    @device.setter
    def device(self, device):
        """Set parent UpnpDevice."""
        if self._device:
            raise UpnpError('UpnpService already bound to UpnpDevice')

        self._device = device

    @property
    def service_type(self):
        """Get service type for this UpnpService."""
        return self._service_description['service_type']

    @property
    def service_id(self):
        """Get service ID for this UpnpService."""
        return self._service_description['service_id']

    @property
    def scpd_url(self):
        """Get full SCPD-url for this UpnpService."""
        return urllib.parse.urljoin(self.device.device_url,
                                    self._service_description['scpd_url'])

    @property
    def control_url(self):
        """Get full control-url for this UpnpService."""
        return urllib.parse.urljoin(self.device.device_url,
                                    self._service_description['control_url'])

    @property
    def event_sub_url(self):
        """Get full event sub-url for this UpnpService."""
        return urllib.parse.urljoin(self.device.device_url,
                                    self._service_description['event_sub_url'])

    @property
    def state_variables(self):
        """Get All UpnpStateVariables for this UpnpService."""
        return self._state_variables

    def state_variable(self, name):
        """Get UPnpStateVariable by name."""
        return self.state_variables.get(name, None)

    @property
    def actions(self):
        """Get All UpnpActions for this UpnpService."""
        return self._actions

    def action(self, name):
        """Get UPnpAction by name."""
        return self.actions.get(name, None)

    @asyncio.coroutine
    def async_call_action(self, action, **kwargs):
        """
        Call a UpnpAction.
        Parameters are in Python-values and coerced automatically to UPnP values.
        """
        if isinstance(action, str):
            action = self.actions[action]

        result = yield from action.async_call(**kwargs)
        return result

    @property
    def subscription_sid(self):
        """Return our current subscription ID for events."""
        return self._subscription_sid

    @asyncio.coroutine
    def async_subscribe(self, callback_uri):
        """SUBSCRIBE for events on StateVariables."""
        if self._subscription_sid:
            raise RuntimeError('Already subscribed, unsubscribe first')

        headers = {
            'NT': 'upnp:event',
            'TIMEOUT': 'Second-infinite',
            'Host': urllib.parse.urlparse(self.event_sub_url).netloc,
            'CALLBACK': '<{}>'.format(callback_uri),
        }
        response_status, response_headers, _ = \
            yield from self._requester.async_http_request('SUBSCRIBE', self.event_sub_url, headers)

        if response_status != 200:
            _LOGGER.error('Did not receive 200, but %s', response_status)
            return

        if 'sid' not in response_headers:
            _LOGGER.error('Did not receive a "SID"')
            return

        subscription_sid = response_headers['sid']
        self._subscription_sid = subscription_sid
        _LOGGER.debug('%s.subscribe(): Got SID: %s', self, subscription_sid)
        return subscription_sid

    @asyncio.coroutine
    def async_unsubscribe(self, force=False):
        """UNSUBSCRIBE from events on StateVariables."""
        if not force and not self._subscription_sid:
            raise RuntimeError('Cannot unsubscribed, subscribe first')

        subscription_sid = self._subscription_sid
        if force:
            # we don't care what happens further, make sure we are unsubscribed
            self._subscription_sid = None

        headers = {
            'Host': urllib.parse.urlparse(self.event_sub_url).netloc,
            'SID': subscription_sid,
        }
        try:
            response_status, _, _ = \
                yield from self._requester.async_http_request('UNSUBSCRIBE',
                                                              self.event_sub_url,
                                                              headers)
        except asyncio.TimeoutError:
            if not force:
                raise
            return

        if response_status != 200:
            _LOGGER.error('Did not receive 200, but %s', response_status)
            return

        self._subscription_sid = None

    def on_notify(self, headers, body):
        """
        Callback for UpnpNotifyView.
        Parses the headers/body and sets UpnpStateVariables with new values.
        """
        notify_sid = headers.get('SID')
        if notify_sid != self._subscription_sid:
            # _LOGGER.debug('Received NOTIFY for unknown SID: %s, known SID: %s',
            #               notify_sid, self._subscription_sid)
            return

        el_root = ET.fromstring(body)
        el_last_change = el_root.find('.//LastChange')
        if el_last_change is None:
            _LOGGER.debug("Got NOTIFY without body, ignoring")
            return

        changed_state_variables = []
        el_event = ET.fromstring(el_last_change.text)
        for el_instance_id in el_event.findall('./'):
            for el_state_var in el_instance_id .findall('./'):
                name = el_state_var.tag.split('}')[1]
                value = el_state_var.get('val')

                state_var = self.state_variable(name)
                if not state_var:
                    continue

                try:
                    state_var.upnp_value = value
                except vol.error.MultipleInvalid:
                    _LOGGER.error('Got invalid value for %s: %s', state_var, value)

                changed_state_variables.append(state_var)

                _LOGGER.debug('%s.on_notify(): set state var %s to %s', self, name, value)

        self.notify_changed_state_variables(changed_state_variables)

    def notify_changed_state_variables(self, changed_state_variables):
        """Callback on UpnpStateVariable.value changes."""
        if self._on_state_variable_change:
            self._on_state_variable_change(self, changed_state_variables)

    @property
    def on_state_variable_change(self):
        """Get callback for value changes."""
        return self._on_state_variable_change

    @on_state_variable_change.setter
    def on_state_variable_change(self, callback):
        """Set callback for value changes."""
        self._on_state_variable_change = callback

    def __str__(self):
        return "<UpnpService({0})>".format(self.service_id)

    def __repr__(self):
        return "<UpnpService({0})>".format(self.service_id)


class UpnpAction(object):
    """Representation of an Action"""

    class Argument(object):
        """Representation of an Argument of an Action"""

        def __init__(self, name, direction, related_state_variable):
            self.name = name
            self.direction = direction
            self.related_state_variable = related_state_variable
            self._value = None

        def validate_value(self, value):
            """Validate value against related UpnpStateVariable."""
            self.related_state_variable.validate_value(value)

        @property
        def value(self):
            """Get Python value for this argument."""
            return self._value

        @value.setter
        def value(self, value):
            """Set Python value for this argument."""
            self.validate_value(value)
            self._value = value

        @property
        def upnp_value(self):
            """Get UPnP value for this argument."""
            return self.coerce_upnp(self.value)

        @upnp_value.setter
        def upnp_value(self, upnp_value):
            """Set UPnP value for this argument."""
            self._value = self.coerce_python(upnp_value)

        def coerce_python(self, upnp_value):
            """Coerce UPnP value to Python."""
            return self.related_state_variable.coerce_python(upnp_value)

        def coerce_upnp(self, value):
            """Coerce Python value to UPnP value."""
            return self.related_state_variable.coerce_upnp(value)

    def __init__(self, name, args):
        self._name = name
        self._args = args

        self._service = None

    @property
    def service(self):
        """Get parent UpnpService."""
        return self._service

    @service.setter
    def service(self, service):
        """Set parent UpnpService."""
        if self.service:
            raise UpnpError('UpnpAction already bound to UpnpService')

        self._service = service

    @property
    def name(self):
        """Get name of this UpnpAction."""
        return self._name

    def __str__(self):
        return "<UpnpService.Action({0})>".format(self.name)

    def validate_arguments(self, **kwargs):
        """Validate arguments against in-arguments of self.
        The python type is expected."""
        for arg in self.in_arguments():
            value = kwargs[arg.name]
            arg.validate_value(value)

    def in_arguments(self):
        """Get all in-arguments."""
        return [arg for arg in self._args if arg.direction == 'in']

    def out_arguments(self):
        """Get all out-arguments."""
        return [arg for arg in self._args if arg.direction == 'out']

    def argument(self, name, direction=None):
        """Get an UpnpAction.Argument by name (and possibliy direction.)"""
        for arg in self._args:
            if arg.name != name:
                continue
            if direction is not None and arg.direction != direction:
                continue

            return arg

    @asyncio.coroutine
    def async_call(self, **kwargs):
        """Call an action with arguments"""
        # build request
        url, headers, body = self.create_request(**kwargs)
        _LOGGER_TRAFFIC.debug('Sending request:\nPOST %s\n%s\n\n%s',
                              url,
                              '\n'.join([key + ": " + value for key, value in headers.items()]),
                              body)

        # do request
        status_code, response_headers, response_body = \
            yield from self.service._requester.async_http_request('POST', url, headers, body)
        _LOGGER_TRAFFIC.debug('Got response:\n%s\n%s\n\n%s',
                              status_code,
                              '\n'.join([key + ": " + value for key, value in response_headers.items()]),
                              response_body)

        if status_code != 200:
            raise UpnpError('Error during async_call(), status: %s, body: %s' % (status_code, response_body))

        # parse body
        response_args = self.parse_response(self.service.service_type,
                                            response_headers,
                                            response_body)
        return response_args

    def create_request(self, **kwargs):
        """Create headers and headers for this to-be-called UpnpAction."""
        # build URL
        control_url = self.service.control_url

        # construct SOAP body
        service_type = self.service.service_type
        soap_args = self._format_request_args(**kwargs)
        body = """<?xml version="1.0"?>
        <s:Envelope s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/" xmlns:s="http://schemas.xmlsoap.org/soap/envelope/">
          <s:Body>
            <u:{1} xmlns:u="{0}">
                {2}
            </u:{1}>
           </s:Body>
        </s:Envelope>""".format(service_type, self.name, soap_args)

        # construct SOAP header
        soap_action = "{0}#{1}".format(service_type, self.name)
        headers = {
            'SOAPAction': u'"{0}"'.format(soap_action),
            'Host': urllib.parse.urlparse(control_url).netloc,
            'Content-Type': 'text/xml',
            'Content-Length': str(len(body)),
        }

        return control_url, headers, body

    def _format_request_args(self, **kwargs):
        self.validate_arguments(**kwargs)
        arg_strs = ["<{0}>{1}</{0}>".format(arg.name, escape(arg.coerce_upnp(kwargs[arg.name])))
                    for arg in self.in_arguments()]
        return "\n".join(arg_strs)

    def parse_response(self, service_type, response_headers, response_body):
        """Parse response from called Action."""
        xml = ET.fromstring(response_body)

        query = './/soap_envelope:Body/soap_envelope:Fault'
        if xml.find(query, NS):
            error_code = xml.find('.//control:errorCode', NS).text
            error_description = xml.find('.//control:errorDescription', NS).text
            raise UpnpError('Error during call_action, error_code: %s, error_description: %s',
                            error_code, error_description)

        return self._parse_response_args(service_type, xml)

    def _parse_response_args(self, service_type, xml):
        args = {}
        query = ".//{{{0}}}{1}Response".format(service_type, self.name)
        response = xml.find(query, NS)
        for arg_xml in response.findall('./'):
            name = arg_xml.tag
            arg = self.argument(name, 'out')

            arg.upnp_value = unescape(arg_xml.text)
            args[name] = arg.value

        return args


class UpnpStateVariable(object):
    """Representation of a State Variable."""

    def __init__(self, state_variable_info, schema):
        self._state_variable_info = state_variable_info
        self._schema = schema

        self._service = None
        self._value = None
        self._updated_at = None

    @property
    def service(self):
        """Get parent UpnpService."""
        return self._service

    @service.setter
    def service(self, service):
        """Set parent UpnpService."""
        if self.service:
            raise UpnpError('UpnpStateVariable already bound to UpnpService')

        self._service = service

    @property
    def min_value(self):
        """Min value for this UpnpStateVariable, if defined."""
        type_info = self._state_variable_info['type_info']
        data_type = type_info['data_type_python']
        min_ = type_info.get('allowed_value_range', {}).get('min')
        if data_type == int and min_ is not None:
            return data_type(min_)

    @property
    def max_value(self):
        """Max value for this UpnpStateVariable, if defined."""
        type_info = self._state_variable_info['type_info']
        data_type = type_info['data_type_python']
        max_ = type_info.get('allowed_value_range', {}).get('max')
        if data_type == int and max_ is not None:
            return data_type(max_)

    @property
    def allowed_values(self):
        """List with allowed values for this UpnpStateVariable, if defined."""
        return self._state_variable_info['type_info'].get('allowed_values', [])

    @property
    def send_events(self):
        """Does this UpnpStatevariable send events?"""
        return self._state_variable_info['send_events']

    @property
    def name(self):
        """Name of the UpnpStatevariable."""
        return self._state_variable_info['name']

    @property
    def data_type(self):
        """Python datatype of UpnpStateVariable."""
        return self._state_variable_info['type_info']['data_type']

    @property
    def default_value(self):
        """Default value for UpnpStateVariable, if defined."""
        data_type = self._state_variable_info['type_info']['data_type_python']
        default_value = self._state_variable_info['type_info'].get('default_value', None)
        if default_value:
            return data_type(default_value)

    def validate_value(self, value):
        """Validate value"""
        self._schema({'value': value})

    @property
    def value(self):
        """Get the value, python typed."""
        return self._value

    @value.setter
    def value(self, value):
        """Set value, python typed."""
        self.validate_value(value)
        self._value = value
        self._updated_at = datetime.now(timezone.utc)

    @property
    def upnp_value(self):
        """Get the value, UPnP typed."""
        return self.coerce_upnp(self.value)

    @upnp_value.setter
    def upnp_value(self, upnp_value):
        """Set the value, UPnP typed."""
        self.value = self.coerce_python(upnp_value)

    def coerce_python(self, upnp_value):
        """Coerce value from UPNP to python."""
        data_type = self._state_variable_info['type_info']['data_type_python']
        if data_type == bool:
            return upnp_value == '1'
        return data_type(upnp_value)

    def coerce_upnp(self, value):
        """Coerce value from python to UPNP."""
        data_type = self._state_variable_info['type_info']['data_type_python']
        if data_type == bool:
            return '1' if value else '0'
        return str(value)

    @property
    def updated_at(self):
        """
        Get timestamp at which this UpnpStateVariable was updated.
        Return time in UTC.
        """
        return self._updated_at

    def __str__(self):
        return "<StateVariable({0}, {1})>".format(self.name, self.data_type)


class UpnpFactory(object):
    """
    Factory for UpnpService and friends.
    Use UpnpFactory.async_create_services() to instantiate UpnpServices from a device XML.
    You have probably received this URL from netdisco, for example.
    """

    STATE_VARIABLE_TYPE_MAPPING = {
        'ui1': int,
        'ui2': int,
        'ui4': int,
        'i1': int,
        'i2': int,
        'i4': int,
        'int': int,
        'r4': float,
        'r8': float,
        'number': float,
        'fixed.14.4': float,
        'float': float,
        'char': chr,
        'string': str,
        'boolean': bool,
        'bin.base64': str,
        'bin.hex': str,
        'uri': str,
        'uuid': str,
    }

    def __init__(self, requester):
        self.requester = requester

    @asyncio.coroutine
    def async_create_device(self, dmr_url):
        """Create a UpnpDevice, with all of it UpnpServices."""
        root = yield from self._async_fetch_device_description(dmr_url)

        # get name
        device_desc = self._device_parse_xml(root)

        # get services
        services = []
        for service_desc_xml in root.findall('.//device:serviceList/device:service', NS):
            service = yield from self.async_create_service(service_desc_xml, dmr_url)
            services.append(service)

        return UpnpDevice(self.requester, dmr_url, device_desc, services)

    # pylint: disable=no-self-use
    def _device_parse_xml(self, device_description_xml):
        return {
            'device_type': device_description_xml.find('.//device:deviceType', NS).text,
            'friendly_name': device_description_xml.find('.//device:friendlyName', NS).text,
            'manufacturer': device_description_xml.find('.//device:manufacturer', NS).text,
            'model_description': device_description_xml.find('.//device:modelDescription', NS).text,
            'model_name': device_description_xml.find('.//device:modelName', NS).text,
        }

    @asyncio.coroutine
    def async_create_service(self, service_description_xml, base_url):
        """Retrieve the SCPD for a service and create a UpnpService from it."""
        scpd_url = service_description_xml.find('device:SCPDURL', NS).text
        scpd_url = urllib.parse.urljoin(base_url, scpd_url)
        scpd_xml = yield from self._async_fetch_scpd(scpd_url)
        return self.create_service(service_description_xml, base_url, scpd_xml)

    def create_service(self, service_description_xml, base_url, scpd_xml):
        """Create a UnpnpService, with UpnpActions and UpnpStateVariables from scpd_xml."""
        service_description = self._service_parse_xml(service_description_xml)
        state_vars = self.create_state_variables(scpd_xml)
        actions = self.create_actions(scpd_xml, state_vars)

        return UpnpService(self.requester, service_description, state_vars, actions)

    # pylint: disable=no-self-use
    def _service_parse_xml(self, service_description_xml):
        return {
            'service_id': service_description_xml.find('device:serviceId', NS).text,
            'service_type': service_description_xml.find('device:serviceType', NS).text,
            'control_url': service_description_xml.find('device:controlURL', NS).text,
            'event_sub_url': service_description_xml.find('device:eventSubURL', NS).text,
            'scpd_url': service_description_xml.find('device:SCPDURL', NS).text,
        }

    def create_state_variables(self, scpd_xml):
        """Create UpnpStateVariables from scpd_xml."""
        state_vars = []
        for state_var_xml in scpd_xml.findall('.//service:stateVariable', NS):
            state_var = self.create_state_variable(state_var_xml)
            state_vars.append(state_var)
        return state_vars

    def create_state_variable(self, state_variable_xml):
        """Create UpnpStateVariable from state_variable_xml"""
        state_variable_info = self._state_variable_parse_xml(state_variable_xml)
        type_info = state_variable_info['type_info']
        schema = self._state_variable_create_schema(type_info)
        return UpnpStateVariable(state_variable_info, schema)

    # pylint: disable=no-self-use
    def _state_variable_parse_xml(self, state_variable_xml):
        info = {
            'name': state_variable_xml.find('service:name', NS).text,
            'type_info': {}
        }
        type_info = info['type_info']

        # send events
        if 'sendEvents' in state_variable_xml.attrib:
            info['send_events'] = state_variable_xml.attrib['sendEvents'] == 'yes'
        else:
            info['send_events'] = state_variable_xml.find('service:sendEventsAttribute', NS).text == 'yes'

        data_type = state_variable_xml.find('service:dataType', NS).text
        type_info['data_type'] = data_type
        type_info['data_type_python'] = UpnpFactory.STATE_VARIABLE_TYPE_MAPPING[data_type]

        default_value = state_variable_xml.find('service:defaultValue', NS)
        if default_value:
            type_info['default_value'] = default_value.text
            type_info['default_type_coerced'] = data_type(default_value.text)

        allowed_value_range = state_variable_xml.find('service:allowedValueRange', NS)
        if allowed_value_range:
            type_info['allowed_value_range'] = {
                'min': allowed_value_range.find('service:minimum', NS).text,
                'max': allowed_value_range.find('service:maximum', NS).text,
            }
            if allowed_value_range.find('service:step', NS):
                type_info['allowed_value_range']['step'] = \
                    allowed_value_range.find('service:step', NS).text

        allowed_value_list = state_variable_xml.find('service:allowedValueList', NS)
        if allowed_value_list:
            type_info['allowed_values'] = \
                [v.text for v in allowed_value_list.findall('service:allowedValue', NS)]

        return info

    # pylint: disable=no-self-use
    def _state_variable_create_schema(self, type_info):
        # construct validators
        validators = []

        data_type = type_info['data_type_python']
        validators.append(data_type)

        if 'allowed_values' in type_info:
            allowed_values = type_info['allowed_values']
            in_ = vol.In(allowed_values)  # coerce allowed values? assume always string for now
            validators.append(in_)

        if 'allowed_value_range' in type_info:
            min_ = type_info['allowed_value_range'].get('min', None)
            max_ = type_info['allowed_value_range'].get('max', None)
            min_ = data_type(min_)
            max_ = data_type(max_)
            range_ = vol.Range(min=min_, max=max_)
            validators.append(range_)

        # construct key
        key = vol.Required('value')

        if 'default_value' in type_info:
            default_value = type_info['default_value']
            if data_type == bool:
                default_value = default_value == '1'
            else:
                default_value = data_type(default_value)
            key.default = default_value

        return vol.Schema({key: vol.All(*validators)})

    def create_actions(self, scpd_xml, state_variables):
        """Create UpnpActions from scpd_xml."""
        actions = []
        for action_xml in scpd_xml.findall('.//service:action', NS):
            action = self.create_action(action_xml, state_variables)
            actions.append(action)
        return actions

    def create_action(self, action_xml, state_variables):
        """Create a UpnpAction from action_xml."""
        action_info = self._action_parse_xml(action_xml, state_variables)
        args = [UpnpAction.Argument(arg_info['name'],
                                    arg_info['direction'],
                                    arg_info['state_variable'])
                for arg_info in action_info['arguments']]
        return UpnpAction(action_info['name'], args)

    def _action_parse_xml(self, action_xml, state_variables):  # pylint: disable=no-self-use
        svs = {sv.name: sv for sv in state_variables}
        info = {
            'name': action_xml.find('service:name', NS).text,
            'arguments': [],
        }
        for argument_xml in action_xml.findall('.//service:argument', NS):
            state_variable_name = argument_xml.find('service:relatedStateVariable', NS).text
            argument = {
                'name': argument_xml.find('service:name', NS).text,
                'direction': argument_xml.find('service:direction', NS).text,
                'state_variable': svs[state_variable_name],
            }
            info['arguments'].append(argument)
        return info

    @asyncio.coroutine
    def _async_fetch_device_description(self, url):
        status_code, _, response_body = yield from self.requester.async_http_request('GET', url)

        if status_code != 200:
            raise UpnpError

        root = ET.fromstring(response_body)
        return root

    @asyncio.coroutine
    def _async_fetch_scpd(self, url):
        status_code, _, response_body = yield from self.requester.async_http_request('GET', url)

        if status_code != 200:
            raise UpnpError

        root = ET.fromstring(response_body)
        return root
