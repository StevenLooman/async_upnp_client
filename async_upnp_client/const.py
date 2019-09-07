# -*- coding: utf-8 -*-
"""Constants module."""

from datetime import date
from datetime import datetime
from datetime import time

from typing import Any, Callable, List, Mapping, NamedTuple, Optional, Sequence  # noqa: F401

from xml.etree import ElementTree as ET
from voluptuous import Invalid  # type: ignore


NS = {
    'soap_envelope': 'http://schemas.xmlsoap.org/soap/envelope/',
    'device': 'urn:schemas-upnp-org:device-1-0',
    'service': 'urn:schemas-upnp-org:service-1-0',
    'event': 'urn:schemas-upnp-org:event-1-0',
    'control': 'urn:schemas-upnp-org:control-1-0',
}


def require_tzinfo(value: Any) -> Any:
    """Require tzinfo."""
    if value.tzinfo is None:
        raise Invalid('Requires tzinfo')
    return value


STATE_VARIABLE_TYPE_MAPPING = {
    'ui1': {'type': int, 'in': int, 'out': str},
    'ui2': {'type': int, 'in': int, 'out': str},
    'ui4': {'type': int, 'in': int, 'out': str},
    'i1': {'type': int, 'in': int, 'out': str},
    'i2': {'type': int, 'in': int, 'out': str},
    'i4': {'type': int, 'in': int, 'out': str},
    'int': {'type': int, 'in': int, 'out': str},
    'r4': {'type': float, 'in': float, 'out': str},
    'r8': {'type': float, 'in': float, 'out': str},
    'number': {'type': float, 'in': float, 'out': str},
    'fixed.14.4': {'type': float, 'in': float, 'out': str},
    'float': {'type': float, 'in': float, 'out': str},
    'char': {'type': str, 'in': str, 'out': str},
    'string': {'type': str, 'in': str, 'out': str},
    'boolean': {
        'type': bool,
        'in': lambda s: s.lower() in ['1', 'true', 'yes'],
        'out': lambda b: '1' if b else '0'
    },
    'bin.base64': {'type': str, 'in': str, 'out': str},
    'bin.hex': {'type': str, 'in': str, 'out': str},
    'uri': {'type': str, 'in': str, 'out': str},
    'uuid': {'type': str, 'in': str, 'out': str},
    'date': {
        'type': date,
        'in': lambda s: datetime.strptime(s, "%Y-%m-%d").date(),
        'out': lambda d: d.isoformat()
    },
    'dateTime': {
        'type': datetime,
        'in': lambda s: datetime.strptime(s, "%Y-%m-%dT%H:%M:%S"),
        'out': lambda dt: dt.isoformat('T', 'seconds')
    },
    'dateTime.tz': {
        'type': datetime,
        'validator': require_tzinfo,
        'in': lambda s: datetime.strptime(s, "%Y-%m-%dT%H:%M:%S%z"),
        'out': lambda dt: dt.isoformat('T', 'seconds')
    },
    'time': {
        'type': time,
        'in': lambda s: datetime.strptime(s, "%H:%M:%S").time(),
        'out': lambda t: t.isoformat('seconds')
    },
    'time.tz': {
        'type': time,
        'validator': require_tzinfo,
        'in': lambda s: datetime.strptime(s, "%H:%M:%S%z").timetz(),
        'out': lambda t: t.isoformat('T', 'seconds')
    },
}  # type: Mapping[str, Mapping[str, Callable]]

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
    ('data_type_mapping', Mapping[str, Callable]),
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
