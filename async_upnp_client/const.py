# -*- coding: utf-8 -*-
"""Constants module."""

from typing import Any, Callable, Dict, List, Mapping, NamedTuple, Optional, Sequence  # noqa: F401

from xml.etree import ElementTree as ET


NS = {
    'soap_envelope': 'http://schemas.xmlsoap.org/soap/envelope/',
    'device': 'urn:schemas-upnp-org:device-1-0',
    'service': 'urn:schemas-upnp-org:service-1-0',
    'event': 'urn:schemas-upnp-org:event-1-0',
    'control': 'urn:schemas-upnp-org:control-1-0',
}

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
    'char': str,
    'string': str,
    'boolean': bool,
    'bin.base64': str,
    'bin.hex': str,
    'uri': str,
    'uuid': str,
}  # type: Dict[str, Callable[[str], Any]]

DeviceInfo = NamedTuple('DeviceInfo', [
    ('device_type', str),
    ('friendly_name', str),
    ('manufacturer', str),
    ('model_name', str),
    ('model_number', Optional[str]),
    ('model_description', Optional[str]),
    ('udn', str),
    ('url', str),
    ('xml', ET.Element),
])

ServiceInfo = NamedTuple('ServiceInfo', [
    ('service_id', str),
    ('service_type', str),
    ('control_url', str),
    ('event_sub_url', str),
    ('scpd_url', str),
    ('xml', ET.Element),
])

ActionArgumentInfo = NamedTuple('ActionArgumentInfo', [
    ('name', str),
    ('direction', str),
    ('state_variable_name', str),
    ('xml', ET.Element),
])

ActionInfo = NamedTuple('ActionInfo', [
    ('name', str),
    ('arguments', Sequence[ActionArgumentInfo]),
    ('xml', ET.Element),
])

StateVariableTypeInfo = NamedTuple('StateVariableTypeInfo', [
    ('data_type', str),
    ('data_type_python', Callable[[str], Any]),
    ('default_value', Optional[str]),
    ('allowed_value_range', Mapping[str, Optional[str]]),
    ('allowed_values', Optional[List[str]]),
    ('xml', ET.Element),
])

StateVariableInfo = NamedTuple('StateVariableInfo', [
    ('name', str),
    ('send_events', bool),
    ('type_info', StateVariableTypeInfo),
    ('xml', ET.Element),
])
