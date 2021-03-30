# -*- coding: utf-8 -*-
"""Constants module."""

from datetime import date, datetime, time
from typing import Callable, List, Mapping, NamedTuple, Optional, Sequence
from xml.etree import ElementTree as ET

from async_upnp_client.utils import parse_date_time, require_tzinfo

NS = {
    "soap_envelope": "http://schemas.xmlsoap.org/soap/envelope/",
    "device": "urn:schemas-upnp-org:device-1-0",
    "service": "urn:schemas-upnp-org:service-1-0",
    "event": "urn:schemas-upnp-org:event-1-0",
    "control": "urn:schemas-upnp-org:control-1-0",
}


MIME_TO_UPNP_CLASS_MAPPING: Mapping[str, str] = {
    "audio": "object.item.audioItem",
    "video": "object.item.videoItem",
    "image": "object.item.imageItem",
    "application/dash+xml": "object.item.videoItem",
    "application/x-mpegurl": "object.item.videoItem",
    "application/vnd.apple.mpegurl": "object.item.videoItem",
}


STATE_VARIABLE_TYPE_MAPPING: Mapping[str, Mapping[str, Callable]] = {
    "ui1": {"type": int, "in": int, "out": str},
    "ui2": {"type": int, "in": int, "out": str},
    "ui4": {"type": int, "in": int, "out": str},
    "i1": {"type": int, "in": int, "out": str},
    "i2": {"type": int, "in": int, "out": str},
    "i4": {"type": int, "in": int, "out": str},
    "int": {"type": int, "in": int, "out": str},
    "r4": {"type": float, "in": float, "out": str},
    "r8": {"type": float, "in": float, "out": str},
    "number": {"type": float, "in": float, "out": str},
    "fixed.14.4": {"type": float, "in": float, "out": str},
    "float": {"type": float, "in": float, "out": str},
    "char": {"type": str, "in": str, "out": str},
    "string": {"type": str, "in": str, "out": str},
    "boolean": {
        "type": bool,
        "in": lambda s: s.lower() in ["1", "true", "yes"],
        "out": lambda b: "1" if b else "0",
    },
    "bin.base64": {"type": str, "in": str, "out": str},
    "bin.hex": {"type": str, "in": str, "out": str},
    "uri": {"type": str, "in": str, "out": str},
    "uuid": {"type": str, "in": str, "out": str},
    "date": {"type": date, "in": parse_date_time, "out": lambda d: d.isoformat()},
    "dateTime": {
        "type": datetime,
        "in": parse_date_time,
        "out": lambda dt: dt.isoformat("T", "seconds"),
    },
    "dateTime.tz": {
        "type": datetime,
        "validator": require_tzinfo,
        "in": parse_date_time,
        "out": lambda dt: dt.isoformat("T", "seconds"),
    },
    "time": {
        "type": time,
        "in": parse_date_time,
        "out": lambda t: t.isoformat("seconds"),
    },
    "time.tz": {
        "type": time,
        "validator": require_tzinfo,
        "in": parse_date_time,
        "out": lambda t: t.isoformat("T", "seconds"),
    },
}

DeviceInfo = NamedTuple(
    "DeviceInfo",
    [
        ("device_type", str),
        ("friendly_name", str),
        ("manufacturer", str),
        ("model_name", str),
        ("model_number", Optional[str]),
        ("model_description", Optional[str]),
        ("serial_number", Optional[str]),
        ("udn", str),
        ("url", str),
        ("xml", ET.Element),
    ],
)

ServiceInfo = NamedTuple(
    "ServiceInfo",
    [
        ("service_id", str),
        ("service_type", str),
        ("control_url", str),
        ("event_sub_url", str),
        ("scpd_url", str),
        ("xml", ET.Element),
    ],
)

ActionArgumentInfo = NamedTuple(
    "ActionArgumentInfo",
    [
        ("name", str),
        ("direction", str),
        ("state_variable_name", str),
        ("xml", ET.Element),
    ],
)

ActionInfo = NamedTuple(
    "ActionInfo",
    [
        ("name", str),
        ("arguments", Sequence[ActionArgumentInfo]),
        ("xml", ET.Element),
    ],
)

StateVariableTypeInfo = NamedTuple(
    "StateVariableTypeInfo",
    [
        ("data_type", str),
        ("data_type_mapping", Mapping[str, Callable]),
        ("default_value", Optional[str]),
        ("allowed_value_range", Mapping[str, Optional[str]]),
        ("allowed_values", Optional[List[str]]),
        ("xml", ET.Element),
    ],
)

StateVariableInfo = NamedTuple(
    "StateVariableInfo",
    [
        ("name", str),
        ("send_events", bool),
        ("type_info", StateVariableTypeInfo),
        ("xml", ET.Element),
    ],
)
