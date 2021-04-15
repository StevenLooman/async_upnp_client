# -*- coding: utf-8 -*-
"""UPnP client module."""

import logging
import urllib.parse
from datetime import datetime, timezone
from typing import (
    Any,
    Callable,
    Generic,
    List,
    Mapping,
    Optional,
    Sequence,
    Tuple,
    TypeVar,
    Union,
)
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape

import defusedxml.ElementTree as DET
import voluptuous as vol

from async_upnp_client.const import (
    NS,
    ActionArgumentInfo,
    ActionInfo,
    DeviceInfo,
    ServiceInfo,
    StateVariableInfo,
)

_LOGGER = logging.getLogger(__name__)
_LOGGER_TRAFFIC_UPNP = logging.getLogger("async_upnp_client.traffic.upnp")


EventCallbackType = Callable[["UpnpService", Sequence["UpnpStateVariable"]], None]


class UpnpRequester:
    """
    Abstract base class used for performing async HTTP requests.

    Implement method async_do_http_request() in your concrete class.
    """

    async def async_http_request(
        self,
        method: str,
        url: str,
        headers: Optional[Mapping[str, str]] = None,
        body: Optional[str] = None,
        body_type: str = "text",
    ) -> Tuple[int, Mapping, Union[str, bytes, None]]:
        """
        Do a HTTP request.

        :param method HTTP Method
        :param url URL to call
        :param headers Headers to send
        :param body Body to send
        :param body_type How to interpret body: 'text', 'raw', 'ignore'

        :return status code, headers, body
        """
        # pylint: disable=too-many-arguments
        _LOGGER_TRAFFIC_UPNP.debug(
            "Sending request:\n%s %s\n%s\n%s\n",
            method,
            url,
            "\n".join([key + ": " + value for key, value in (headers or {}).items()]),
            body or "",
        )
        (
            response_status,
            response_headers,
            response_body,
        ) = await self.async_do_http_request(
            method, url, headers=headers, body=body, body_type=body_type
        )

        log_response_body = (
            response_body if body_type == "text" else "async_upnp_client: OMITTING BODY"
        )
        _LOGGER_TRAFFIC_UPNP.debug(
            "Got response:\n%s\n%s\n\n%s",
            response_status,
            "\n".join([key + ": " + value for key, value in response_headers.items()]),
            log_response_body,
        )

        return response_status, response_headers, response_body

    async def async_do_http_request(
        self,
        method: str,
        url: str,
        headers: Optional[Mapping[str, str]] = None,
        body: Optional[str] = None,
        body_type: str = "text",
    ) -> Tuple[int, Mapping, Union[str, bytes, None]]:
        """
        Actually do a HTTP request.

        :param method HTTP Method
        :param url URL to call
        :param headers Headers to send
        :param body Body to send
        :param body_type How to interpret body: 'text', 'raw', 'ignore'

        :return status code, headers, body
        """
        # pylint: disable=too-many-arguments
        raise NotImplementedError()


class UpnpError(Exception):
    """UpnpError."""


class UpnpValueError(UpnpError):
    """Invalid value error."""

    def __init__(self, name: str, value: Any) -> None:
        """Initialize."""
        super().__init__("Invalid value for %s: '%s'" % (name, value))


class UpnpDevice:
    """UPnP Device representation."""

    def __init__(
        self,
        requester: UpnpRequester,
        device_info: DeviceInfo,
        services: Sequence["UpnpService"],
        boot_id: Optional[str] = None,
        config_id: Optional[str] = None,
    ) -> None:
        """Initialize."""
        # pylint: disable=too-many-arguments
        self.requester = requester
        self._device_info = device_info
        self.services = {service.service_type: service for service in services}

        # bind services to ourselves
        for service in services:
            service.device = self

        self.boot_id: Optional[str] = boot_id
        self.config_id: Optional[str] = config_id

        # Just initialized, mark available.
        self.available = True

    @property
    def name(self) -> str:
        """Get the name of this device."""
        return self._device_info.friendly_name

    @property
    def friendly_name(self) -> str:
        """Get the friendly name of this device, alias for name."""
        return self._device_info.friendly_name

    @property
    def manufacturer(self) -> str:
        """Get the manufacturer of this device."""
        return self._device_info.manufacturer

    @property
    def model_description(self) -> Optional[str]:
        """Get the model description of this device."""
        return self._device_info.model_description

    @property
    def model_name(self) -> str:
        """Get the model name of this device."""
        return self._device_info.model_name

    @property
    def model_number(self) -> Optional[str]:
        """Get the model number of this device."""
        return self._device_info.model_number

    @property
    def serial_number(self) -> Optional[str]:
        """Get the serial number of this device."""
        return self._device_info.serial_number

    @property
    def udn(self) -> str:
        """Get UDN of this device."""
        return self._device_info.udn

    @property
    def device_url(self) -> str:
        """Get the URL of this device."""
        return self._device_info.url

    @property
    def device_type(self) -> str:
        """Get the device type of this device."""
        return self._device_info.device_type

    @property
    def xml(self) -> ET.Element:
        """Get the XML description for this device."""
        return self._device_info.xml

    def has_service(self, service_type: str) -> bool:
        """Check if service by service_type is available."""
        return service_type in self.services

    def service(self, service_type: str) -> "UpnpService":
        """Get service by service_type."""
        return self.services[service_type]

    def service_id(self, service_id: str) -> Optional["UpnpService"]:
        """Get service by service_id."""
        for service in self.services.values():
            if service.service_id == service_id:
                return service
        return None

    async def async_ping(self) -> None:
        """Ping the device."""
        await self.requester.async_http_request("GET", self.device_url)

    def __str__(self) -> str:
        """To string."""
        return "<UpnpDevice({0})>".format(self.udn)


class UpnpService:
    """UPnP Service representation."""

    # pylint: disable=too-many-instance-attributes

    def __init__(
        self,
        requester: UpnpRequester,
        service_info: ServiceInfo,
        state_variables: Sequence["UpnpStateVariable"],
        actions: Sequence["UpnpAction"],
    ) -> None:
        """Initialize."""
        self.requester = requester
        self._service_info = service_info
        self.state_variables = {sv.name: sv for sv in state_variables}
        self.actions = {ac.name: ac for ac in actions}

        self.on_event: Optional[EventCallbackType] = None
        self._device: Optional[UpnpDevice] = None

        # bind state variables to ourselves
        for state_var in state_variables:
            state_var.service = self

        # bind actions to ourselves
        for action in actions:
            action.service = self

    @property
    def device(self) -> UpnpDevice:
        """Get parent UpnpDevice."""
        if not self._device:
            raise UpnpError("UpnpService not bound to UpnpDevice")

        return self._device

    @device.setter
    def device(self, device: UpnpDevice) -> None:
        """Set parent UpnpDevice."""
        self._device = device

    @property
    def service_type(self) -> str:
        """Get service type for this UpnpService."""
        return self._service_info.service_type

    @property
    def service_id(self) -> str:
        """Get service ID for this UpnpService."""
        return self._service_info.service_id

    @property
    def scpd_url(self) -> str:
        """Get full SCPD-url for this UpnpService."""
        url: str = urllib.parse.urljoin(
            self.device.device_url, self._service_info.scpd_url
        )
        return url

    @property
    def control_url(self) -> str:
        """Get full control-url for this UpnpService."""
        url: str = urllib.parse.urljoin(
            self.device.device_url, self._service_info.control_url
        )
        return url

    @property
    def event_sub_url(self) -> str:
        """Get full event sub-url for this UpnpService."""
        url: str = urllib.parse.urljoin(
            self.device.device_url, self._service_info.event_sub_url
        )
        return url

    @property
    def xml(self) -> ET.Element:
        """Get the XML description for this service."""
        return self._service_info.xml

    def has_state_variable(self, name: str) -> bool:
        """Check if self has state variable called name."""
        if name not in self.state_variables and "}" in name:
            # possibly messed up namespaces, try again without namespace
            name = name.split("}")[1]

        return name in self.state_variables

    def state_variable(self, name: str) -> "UpnpStateVariable":
        """Get UPnpStateVariable by name."""
        state_var = self.state_variables.get(name, None)

        # possibly messed up namespaces, try again without namespace
        if not state_var and "}" in name:
            name = name.split("}")[1]
            state_var = self.state_variables.get(name, None)

        if state_var is None:
            raise KeyError(name)

        return state_var

    def has_action(self, name: str) -> bool:
        """Check if self has action called name."""
        return name in self.actions

    def action(self, name: str) -> "UpnpAction":
        """Get UPnpAction by name."""
        return self.actions[name]

    async def async_call_action(
        self, action: "UpnpAction", **kwargs: Any
    ) -> Mapping[str, Any]:
        """
        Call a UpnpAction.

        Parameters are in Python-values and coerced automatically to UPnP values.
        """
        if isinstance(action, str):
            action = self.actions[action]

        result = await action.async_call(**kwargs)
        return result

    def notify_changed_state_variables(self, changes: Mapping[str, str]) -> None:
        """Do callback on UpnpStateVariable.value changes."""
        changed_state_variables = []

        for name, value in changes.items():
            if not self.has_state_variable(name):
                _LOGGER.debug("State variable %s does not exist, ignoring", name)
                continue

            state_var = self.state_variable(name)
            try:
                state_var.upnp_value = value
                changed_state_variables.append(state_var)
            except UpnpValueError:
                _LOGGER.error("Got invalid value for %s: %s", state_var, value)

        if self.on_event:
            # pylint: disable=not-callable
            self.on_event(self, changed_state_variables)

    def __str__(self) -> str:
        """To string."""
        udn = "unbound"
        if self._device:
            udn = self._device.udn
        return "<UpnpService({}, {})>".format(self.service_id, udn)

    def __repr__(self) -> str:
        """To repr."""
        udn = "unbound"
        if self._device:
            udn = self._device.udn
        return "<UpnpService({}, {})>".format(self.service_id, udn)


class UpnpAction:
    """Representation of an Action."""

    class Argument:
        """Representation of an Argument of an Action."""

        def __init__(
            self, argument_info: ActionArgumentInfo, state_variable: "UpnpStateVariable"
        ) -> None:
            """Initialize."""
            self._argument_info = argument_info
            self._related_state_variable = state_variable
            self._value = None
            self.raw_upnp_value: Optional[str] = None

        def validate_value(self, value: Any) -> None:
            """Validate value against related UpnpStateVariable."""
            self.related_state_variable.validate_value(value)

        @property
        def name(self) -> str:
            """Get the name."""
            return self._argument_info.name

        @property
        def direction(self) -> str:
            """Get the direction."""
            return self._argument_info.direction

        @property
        def related_state_variable(self) -> "UpnpStateVariable":
            """Get the related state variable."""
            return self._related_state_variable

        @property
        def xml(self) -> ET.Element:
            """Get the XML description for this device."""
            return self._argument_info.xml

        @property
        def value(self) -> Any:
            """Get Python value for this argument."""
            return self._value

        @value.setter
        def value(self, value: Any) -> None:
            """Set Python value for this argument."""
            self.validate_value(value)
            self._value = value

        @property
        def upnp_value(self) -> str:
            """Get UPnP value for this argument."""
            return self.coerce_upnp(self.value)

        @upnp_value.setter
        def upnp_value(self, upnp_value: str) -> None:
            """Set UPnP value for this argument."""
            self._value = self.coerce_python(upnp_value)

        def coerce_python(self, upnp_value: str) -> Any:
            """Coerce UPnP value to Python."""
            return self.related_state_variable.coerce_python(upnp_value)

        def coerce_upnp(self, value: Any) -> str:
            """Coerce Python value to UPnP value."""
            return self.related_state_variable.coerce_upnp(value)

        def __repr__(self) -> str:
            """To repr."""
            return "<UpnpAction.Argument({}, {})>".format(self.name, self.direction)

    def __init__(
        self,
        action_info: ActionInfo,
        arguments: List["UpnpAction.Argument"],
        disable_unknown_out_argument_error: bool = False,
    ) -> None:
        """Initialize."""
        self._action_info = action_info
        self._arguments = arguments
        self._service: Optional[UpnpService] = None
        self._properties = {
            "disable_unknown_out_argument_error": disable_unknown_out_argument_error,
        }

    @property
    def name(self) -> str:
        """Get the name."""
        return self._action_info.name

    @property
    def arguments(self) -> List["UpnpAction.Argument"]:
        """Get the arguments."""
        return self._arguments

    @property
    def xml(self) -> ET.Element:
        """Get the XML for this action."""
        return self._action_info.xml

    @property
    def service(self) -> UpnpService:
        """Get parent UpnpService."""
        if not self._service:
            raise UpnpError("UpnpAction not bound to UpnpService")

        return self._service

    @service.setter
    def service(self, service: UpnpService) -> None:
        """Set parent UpnpService."""
        self._service = service

    def __str__(self) -> str:
        """To string."""
        return "<UpnpAction({0})>".format(self.name)

    def __repr__(self) -> str:
        """To repr."""
        return "<UpnpAction({0})({1}) -> {2}>".format(
            self.name, self.in_arguments(), self.out_arguments()
        )

    def validate_arguments(self, **kwargs: Any) -> None:
        """
        Validate arguments against in-arguments of self.

        The python type is expected.
        """
        for arg in self.in_arguments():
            if arg.name not in kwargs:
                raise UpnpError(f"Missing argument: {arg.name}")

            value = kwargs[arg.name]
            arg.validate_value(value)

    def in_arguments(self) -> List["UpnpAction.Argument"]:
        """Get all in-arguments."""
        return [arg for arg in self.arguments if arg.direction == "in"]

    def out_arguments(self) -> List["UpnpAction.Argument"]:
        """Get all out-arguments."""
        return [arg for arg in self.arguments if arg.direction == "out"]

    def argument(
        self, name: str, direction: Optional[str] = None
    ) -> Optional["UpnpAction.Argument"]:
        """Get an UpnpAction.Argument by name (and possibliy direction)."""
        for arg in self.arguments:
            if arg.name != name:
                continue
            if direction is not None and arg.direction != direction:
                continue

            return arg
        return None

    async def async_call(self, **kwargs: Any) -> Mapping[str, Any]:
        """Call an action with arguments."""
        # do request
        url, headers, body = self.create_request(**kwargs)
        (
            status_code,
            response_headers,
            response_body,
        ) = await self.service.requester.async_http_request("POST", url, headers, body)
        if not isinstance(response_body, str):
            raise UpnpError("Did not receive a body")

        if status_code != 200:
            raise UpnpError(
                "Error during async_call(), status: %s, body: %s"
                % (status_code, response_body)
            )

        # parse body
        response_args = self.parse_response(
            self.service.service_type, response_headers, response_body
        )
        return response_args

    def create_request(self, **kwargs: Any) -> Tuple[str, Mapping[str, str], str]:
        """Create headers and headers for this to-be-called UpnpAction."""
        # build URL
        control_url = self.service.control_url

        # construct SOAP body
        service_type = self.service.service_type
        soap_args = self._format_request_args(**kwargs)
        body = (
            '<?xml version="1.0"?>'
            '<s:Envelope s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/"'
            ' xmlns:s="http://schemas.xmlsoap.org/soap/envelope/">'
            "<s:Body>"
            '<u:{1} xmlns:u="{0}">'
            "{2}"
            "</u:{1}>"
            "</s:Body>"
            "</s:Envelope>".format(service_type, self.name, soap_args)
        )

        # construct SOAP header
        soap_action = "{0}#{1}".format(service_type, self.name)
        headers = {
            "SOAPAction": '"{0}"'.format(soap_action),
            "Host": urllib.parse.urlparse(control_url).netloc,
            "Content-Type": 'text/xml; charset="utf-8"',
            "Content-Length": str(len(body)),
        }

        return control_url, headers, body

    def _format_request_args(self, **kwargs: Any) -> str:
        self.validate_arguments(**kwargs)
        arg_strs = [
            "<{0}>{1}</{0}>".format(arg.name, escape(arg.coerce_upnp(kwargs[arg.name])))
            for arg in self.in_arguments()
        ]
        return "\n".join(arg_strs)

    def parse_response(
        self, service_type: str, response_headers: Mapping, response_body: str
    ) -> Mapping[str, Any]:
        """Parse response from called Action."""
        # pylint: disable=unused-argument
        xml = DET.fromstring(response_body)

        query = ".//soap_envelope:Body/soap_envelope:Fault"
        if xml.find(query, NS):
            error_code = xml.findtext(".//control:errorCode", None, NS)
            error_description = xml.findtext(".//control:errorDescription", None, NS)
            raise UpnpError(
                "Error during call_action, error_code: %s, error_description: %s"
                % (error_code, error_description)
            )

        try:
            return self._parse_response_args(service_type, xml)
        except AttributeError:
            _LOGGER.debug("Could not parse response: %s", response_body)
            raise

    def _parse_response_args(
        self, service_type: str, xml: ET.Element
    ) -> Mapping[str, Any]:
        """Parse response arguments."""
        args = {}
        query = ".//{{{0}}}{1}Response".format(service_type, self.name)
        response = xml.find(query, NS)
        if response is None:
            raise UpnpError(
                "Invalid response: %s" % (ET.tostring(xml, encoding="unicode"),)
            )

        for arg_xml in response.findall("./"):
            name = arg_xml.tag
            arg = self.argument(name, "out")
            if not arg:
                if self._properties["disable_unknown_out_argument_error"]:
                    continue

                raise UpnpError(
                    "Invalid response, unknown argument: %s, %s"
                    % (name, ET.tostring(xml, encoding="unicode"))
                )

            arg.raw_upnp_value = arg_xml.text
            arg.upnp_value = arg_xml.text or ""
            args[name] = arg.value

        return args


T = TypeVar("T")  # pylint: disable=invalid-name


class UpnpStateVariable(Generic[T]):
    """Representation of a State Variable."""

    UPNP_VALUE_ERROR = object()

    def __init__(
        self, state_variable_info: StateVariableInfo, schema: vol.Schema
    ) -> None:
        """Initialize."""
        self._state_variable_info = state_variable_info
        self._schema = schema

        self._service: Optional[UpnpService] = None
        self._value: Optional[Any] = None  # None, T or UPNP_VALUE_ERROR
        self._updated_at: Optional[datetime] = None

    @property
    def service(self) -> UpnpService:
        """Get parent UpnpService."""
        if not self._service:
            raise UpnpError("UpnpStateVariable not bound to UpnpService")

        return self._service

    @service.setter
    def service(self, service: UpnpService) -> None:
        """Set parent UpnpService."""
        self._service = service

    @property
    def xml(self) -> ET.Element:
        """Get the XML for this State Variable."""
        return self._state_variable_info.xml

    @property
    def data_type_mapping(self) -> Mapping[str, Callable]:
        """Get the data type (coercer) for this State Variable."""
        type_info = self._state_variable_info.type_info
        return type_info.data_type_mapping

    @property
    def data_type_python(self) -> Callable[[str], Any]:
        """Get the Python data type for this State Variable."""
        return self.data_type_mapping["type"]

    @property
    def min_value(self) -> Optional[T]:
        """Min value for this UpnpStateVariable, if defined."""
        type_info = self._state_variable_info.type_info
        min_ = type_info.allowed_value_range.get("min")
        if min_ is not None:
            value: T = self.coerce_python(min_)
            return value

        return None

    @property
    def max_value(self) -> Optional[T]:
        """Max value for this UpnpStateVariable, if defined."""
        type_info = self._state_variable_info.type_info
        max_ = type_info.allowed_value_range.get("max")
        if max_ is not None:
            value: T = self.coerce_python(max_)
            return value

        return None

    @property
    def allowed_values(self) -> List[T]:
        """List with allowed values for this UpnpStateVariable, if defined."""
        type_info = self._state_variable_info.type_info
        allowed_values = type_info.allowed_values or []
        return [self.coerce_python(allowed_value) for allowed_value in allowed_values]

    @property
    def send_events(self) -> bool:
        """Check if this UpnpStatevariable send events."""
        send_events = self._state_variable_info.send_events
        return send_events

    @property
    def name(self) -> str:
        """Name of the UpnpStatevariable."""
        name: str = self._state_variable_info.name
        return name

    @property
    def data_type(self) -> str:
        """UPNP data type of UpnpStateVariable."""
        return self._state_variable_info.type_info.data_type

    @property
    def default_value(self) -> Optional[T]:
        """Get default value for UpnpStateVariable, if defined."""
        type_info = self._state_variable_info.type_info
        default_value = type_info.default_value
        if default_value is not None:
            value: T = self.coerce_python(default_value)
            return value

        return None

    def validate_value(self, value: T) -> None:
        """Validate value."""
        try:
            self._schema(value)
        except vol.error.MultipleInvalid as ex:
            raise UpnpValueError(self.name, value) from ex

    @property
    def value(self) -> Optional[T]:
        """
        Get the value, python typed.

        Invalid values are returned as None.
        """
        if self._value is UpnpStateVariable.UPNP_VALUE_ERROR:
            return None

        return self._value

    @value.setter
    def value(self, value: Any) -> None:
        """Set value, python typed."""
        self.validate_value(value)
        self._value = value
        self._updated_at = datetime.now(timezone.utc)

    @property
    def value_unchecked(self) -> Optional[T]:
        """
        Get the value, python typed.

        If an event was received with an invalid value for this StateVariable
        (e.g., 'abc' for a 'ui4' StateVariable), then this will return
        UpnpStateVariable.UPNP_VALUE_ERROR instead of None.
        """
        return self._value

    @property
    def upnp_value(self) -> str:
        """Get the value, UPnP typed."""
        return self.coerce_upnp(self.value)

    @upnp_value.setter
    def upnp_value(self, upnp_value: str) -> None:
        """Set the value, UPnP typed."""
        try:
            self.value = self.coerce_python(upnp_value)
        except ValueError as err:
            _LOGGER.debug('Error setting upnp_value "%s", error: %s', upnp_value, err)
            self._value = UpnpStateVariable.UPNP_VALUE_ERROR

    def coerce_python(self, upnp_value: str) -> Any:
        """Coerce value from UPNP to python."""
        coercer = self.data_type_mapping["in"]
        return coercer(upnp_value)

    def coerce_upnp(self, value: Any) -> str:
        """Coerce value from python to UPNP."""
        coercer = self.data_type_mapping["out"]
        coerced_value: str = coercer(value)
        return coerced_value

    @property
    def updated_at(self) -> Optional[datetime]:
        """
        Get timestamp at which this UpnpStateVariable was updated.

        Return time in UTC.
        """
        return self._updated_at

    def __str__(self) -> str:
        """To string."""
        return "<UpnpStateVariable({0}, {1})>".format(self.name, self.data_type)
