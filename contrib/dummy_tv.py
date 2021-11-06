import asyncio
import logging
import uuid

import async_timeout
import defusedxml.ElementTree as DET
from aiohttp import ClientSession, web

logging.basicConfig(level=logging.DEBUG)
LOGGER = logging.getLogger(__name__)
PORT = 8000


DET.ElementTree.register_namespace("envelope", "http://schemas.xmlsoap.org/soap/envelope/")
DET.ElementTree.register_namespace("rc_service", "urn:schemas-upnp-org:service:RenderingControl:1")
DET.ElementTree.register_namespace("rcs", "urn:schemas-upnp-org:metadata-1-0/RCS/")

NS = {
    "envelope": "http://schemas.xmlsoap.org/soap/envelope/",
    "device": "urn:schemas-upnp-org:device-1-0",
    "service": "urn:schemas-upnp-org:service-1-0",
    "event": "urn:schemas-upnp-org:event-1-0",
    "rc_service": "urn:schemas-upnp-org:service:RenderingControl:1",
    "rcs": "urn:schemas-upnp-org:metadata-1-0/RCS/",
}

SUBSCRIBED_CLIENTS = {
    "RC": {},
    "AVT": {},
}

STATE_VARIABLES = {
    "RC": {},
    "AVT": {},
}


class StateVariable(object):
    def __init__(self, value):
        self._value = value

    def matches_action(self, command):
        return getattr(self, command, None) is not None

    @asyncio.coroutine
    def do_command(self, command, **kwargs):
        m = getattr(self, command, None)
        r = yield from m(**kwargs)
        return r

    @property
    def name(self):
        return self.__class__.__name__

    @property
    def value(self):
        return self._value

    @asyncio.coroutine
    def async_notify_listeners(self, **kwargs):
        property = str(self.__class__.__name__)
        value = str(self.value)

        LOGGER.debug("async_notify_listeners(): %s -> %s", property, value)

        event_base = (
            '<Event xmlns="urn:schemas-upnp-org:metadata-1-0/RCS/">'
            '<InstanceID val="0" />'
            "</Event>"
        )
        el_event = DET.ElementTree.fromstring(event_base)
        el_instance_id = el_event.find(".//rcs:InstanceID", NS)
        args = kwargs.copy()
        args.update({"val": value})
        DET.ElementTree.SubElement(el_instance_id, "rcs:" + property, **args)

        notify_base = (
            '<?xml version="1.0" encoding="utf-8"?>'
            '<e:propertyset xmlns:e="urn:schemas-upnp-org:event-1-0">'
            "<e:property>"
            "<LastChange />"
            "</e:property>"
            "</e:propertyset>"
        )
        el_notify = DET.ElementTree.fromstring(notify_base)
        el_last_change = el_notify.find(".//LastChange", NS)
        el_last_change.text = DET.ElementTree.tostring(el_event).decode("utf-8")

        global SUBSCRIBED_CLIENTS
        service_name = self.SERVICE_NAME
        for sid, url in SUBSCRIBED_CLIENTS[service_name].items():
            headers = {"SID": sid}
            with ClientSession(loop=asyncio.get_event_loop()) as session:
                async with async_timeout.timeout(10):
                    data = DET.ElementTree.tostring(el_notify)
                    LOGGER.debug("Calling: %s", url)
                    yield from session.request(
                        "NOTIFY", url, headers=headers, data=data
                    )

    def __str__(self):
        return "<{}({}, {})>".format(
            self.__class__.__name__, self.SERVICE_NAME, self.value
        )


class Volume(StateVariable):

    SERVICE_NAME = "RC"

    def __init__(self):
        super().__init__(0)

    @asyncio.coroutine
    def GetVolume(self, **kwargs):
        LOGGER.debug("GetVolume(%s)", kwargs)
        return dict(CurrentVolume=self.value)

    @asyncio.coroutine
    def SetVolume(self, **kwargs):
        LOGGER.debug("SetVolume(%s)", kwargs)
        self._value = kwargs["DesiredVolume"]
        yield from self.async_notify_listeners(InstanceID="0", Channel="Master")
        return dict()


class Mute(StateVariable):

    SERVICE_NAME = "RC"

    def __init__(self):
        super().__init__(0)

    @asyncio.coroutine
    def GetMute(self, **kwargs):
        LOGGER.debug("GetMute(%s)", kwargs)
        return dict(CurrentMute=self.value)

    @asyncio.coroutine
    def SetMute(self, **kwargs):
        LOGGER.debug("SetMute(%s)", kwargs)
        self._value = kwargs["DesiredMute"]
        yield from self.async_notify_listeners(InstanceID="0", Channel="Master")
        return dict()


class TransportState(StateVariable):

    SERVICE_NAME = "AVT"

    def __init__(self):
        # super().__init__('STOPPED')
        super().__init__("PLAYING")

    @asyncio.coroutine
    def GetTransportInfo(self, **kwargs):
        LOGGER.debug("GetTransportState(%s)", kwargs)
        return dict(
            CurrentTransportState=self.value,
            CurrentTransportStatus="OK",
            CurrentSpeed="1.0",
        )


class TrackDuration(StateVariable):

    SERVICE_NAME = "AVT"

    def __init__(self):
        super().__init__("00:10:00")

    @asyncio.coroutine
    def GetPositionInfo(self, **kwargs):
        LOGGER.debug("GetPositionInfo(%s)", kwargs)
        return dict(
            TrackDuration=self.value,
            Track=1,
            TrackMetaData="",
            TrackURI="",
            RelTime="00:05:00",
            AbsTime="00:05:00",
        )


STATE_VARIABLES["RC"]["Volume"] = Volume()
STATE_VARIABLES["RC"]["Mute"] = Mute()
STATE_VARIABLES["AVT"]["TransportState"] = TransportState()
STATE_VARIABLES["AVT"]["TrackDuration"] = TrackDuration()


@asyncio.coroutine
def async_handle_control_rc(request):
    ns = "urn:schemas-upnp-org:service:RenderingControl:1"
    response = yield from async_handle_control(request, STATE_VARIABLES["RC"], ns)
    return response


@asyncio.coroutine
def async_handle_control_avt(request):
    ns = "urn:schemas-upnp-org:service:AVTransport:1"
    response = yield from async_handle_control(request, STATE_VARIABLES["AVT"], ns)
    return response


@asyncio.coroutine
def async_handle_control(request, state_variables, xml_ns):
    body = yield from request.content.read()

    # read command and args
    el_request = DET.ElementTree.fromstring(body)
    el_body = el_request.find("envelope:Body", NS)
    el_command = el_body.find("./")
    command = el_command.tag.split("}")[1]
    args = {el_arg.tag: el_arg.text for el_arg in el_command.findall("./")}
    LOGGER.debug("Command: %s", command)
    LOGGER.debug("Args: %s", args)

    # do command
    result = {}
    for state_var in state_variables.values():
        if state_var.matches_action(command):
            result = yield from state_var.do_command(command, **args)
    if result is None:
        return web.Response(status=404)

    LOGGER.debug("Result: %s", result)

    # return result
    response_base = (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<s:Envelope s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/" xmlns:s="http://schemas.xmlsoap.org/soap/envelope/">'
        "<s:Body />"
        "</s:Envelope>"
    )
    el_envelope = DET.ElementTree.fromstring(response_base)
    el_body = el_envelope.find("./envelope:Body", NS)
    el_response = DET.ElementTree.SubElement(el_body, "{" + xml_ns + "}" + command + "Response")
    for key, value in result.items():
        el_arg = DET.ElementTree.SubElement(el_response, key)
        el_arg.text = str(value)

    text = DET.ElementTree.tostring(el_envelope)
    return web.Response(status=200, body=text)


# region Subscriptions
# region Subscribe
@asyncio.coroutine
def async_handle_subscribe_rc(request):
    response = yield from async_handle_subscribe(
        request, SUBSCRIBED_CLIENTS["RC"], STATE_VARIABLES["RC"]
    )
    return response


@asyncio.coroutine
def async_handle_subscribe_avt(request):
    response = yield from async_handle_subscribe(
        request, SUBSCRIBED_CLIENTS["AVT"], STATE_VARIABLES["AVT"]
    )
    return response


@asyncio.coroutine
def async_handle_subscribe(request, subscribed_clients, state_variables):
    callback_url = request.headers.get("CALLBACK")[1:-1]
    sid = "uuid:" + str(uuid.uuid4())
    subscribed_clients[sid] = callback_url

    headers = {"SID": sid}

    @asyncio.coroutine
    def async_push_later(state_variable):
        yield from asyncio.sleep(0.5)
        yield from state_variable.async_notify_listeners()

    for state_variable in state_variables.values():
        LOGGER.debug("Pushing state_variable on SUBSCRIBE: %s", state_variable.name)
        asyncio.get_event_loop().create_task(async_push_later(state_variable))

    return web.Response(status=200, headers=headers)


# endregion


# region Unsubscribe
@asyncio.coroutine
def async_handle_unsubscribe_rc(request):
    response = yield from async_handle_unsubscribe(request, SUBSCRIBED_CLIENTS["RC"])
    return response


@asyncio.coroutine
def async_handle_unsubscribe_avt(request):
    response = yield from async_handle_unsubscribe(request, SUBSCRIBED_CLIENTS["AVT"])
    return response


@asyncio.coroutine
def async_handle_unsubscribe(request, subscribed_clients):
    sid = request.headers.get("SID")
    if sid not in subscribed_clients:
        return web.Response(status=404)

    del subscribed_clients[sid]
    return web.Response(status=200)


# endregion
# endregion


app = web.Application()
app.router.add_static("/", path="dummy_tv/", name="static")
app.router.add_route("POST", "/upnp/control/RenderingControl1", async_handle_control_rc)
app.router.add_route(
    "SUBSCRIBE", "/upnp/event/RenderingControl1", async_handle_subscribe_rc
)
app.router.add_route(
    "UNSUBSCRIBE", "/upnp/event/RenderingControl1", async_handle_unsubscribe_rc
)

app.router.add_route("POST", "/upnp/control/AVTransport1", async_handle_control_avt)
app.router.add_route(
    "SUBSCRIBE", "/upnp/event/AVTransport1", async_handle_subscribe_avt
)
app.router.add_route(
    "UNSUBSCRIBE", "/upnp/event/AVTransport1", async_handle_unsubscribe_avt
)

web.run_app(app, port=PORT)
