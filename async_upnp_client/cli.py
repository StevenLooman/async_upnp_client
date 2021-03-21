# -*- coding: utf-8 -*-
"""CLI UPnP client module."""
# pylint: disable=invalid-name

import argparse
import asyncio
import json
import logging
import operator
import sys
import time
import urllib.parse
from datetime import datetime
from ipaddress import ip_address
from typing import Any, Mapping, Optional, Sequence, Tuple, Union

from async_upnp_client import UpnpDevice, UpnpFactory, UpnpService, UpnpStateVariable
from async_upnp_client.advertisement import UpnpAdvertisementListener
from async_upnp_client.aiohttp import (
    AiohttpNotifyServer,
    AiohttpRequester,
    get_local_ip,
)
from async_upnp_client.profiles.dlna import dlna_handle_notify_last_change
from async_upnp_client.search import async_search as async_ssdp_search
from async_upnp_client.ssdp import SSDP_ST_ALL

logging.basicConfig()
_LOGGER = logging.getLogger("upnp-client")
_LOGGER.setLevel(logging.ERROR)
_LOGGER_LIB = logging.getLogger("async_upnp_client")
_LOGGER_LIB.setLevel(logging.ERROR)
_LOGGER_TRAFFIC = logging.getLogger("async_upnp_client.traffic")
_LOGGER_TRAFFIC.setLevel(logging.ERROR)

DEFAULT_PORT = 11302


parser = argparse.ArgumentParser(description="upnp_client")
parser.add_argument("--debug", action="store_true", help="Show debug messages")
parser.add_argument("--debug-traffic", action="store_true", help="Show network traffic")
parser.add_argument(
    "--pprint", action="store_true", help="Pretty-print (indent) JSON output"
)
parser.add_argument("--timeout", type=int, help="Timeout for connection", default=5)
parser.add_argument(
    "--strict", action="store_true", help="Be strict about invalid data received"
)
parser.add_argument(
    "--iso8601", action="store_true", help="Print timestamp in ISO8601 format"
)
subparsers = parser.add_subparsers(title="Command", dest="command")
subparsers.required = True

subparser = subparsers.add_parser("call-action", help="Call an action")
subparser.add_argument("device", help="URL to device description XML")
subparser.add_argument(
    "call-action", nargs="+", help="service/action param1=val1 param2=val2"
)
subparser = subparsers.add_parser("subscribe", help="Subscribe to services")
subparser.add_argument("device", help="URL to device description XML")
subparser.add_argument(
    "service", nargs="+", help="service type or part or abbreviation"
)
subparser.add_argument("--bind", help="ip[:port], e.g., 192.168.0.10:8090")
subparser.add_argument(
    "--nolastchange", action="store_true", help="Do not show LastChange events"
)
subparser = subparsers.add_parser("search", help="Search for devices")
subparser.add_argument("--bind", help="ip, e.g., 192.168.0.10")
subparser.add_argument(
    "--target", help="ip, e.g., 192.168.0.10 or FF02::C to request from"
)
subparser.add_argument(
    "--service_type", help="service type to search for", default=SSDP_ST_ALL
)
subparser = subparsers.add_parser("advertisements", help="Listen for advertisements")
subparser.add_argument("--bind", help="ip, e.g., 192.168.0.10")
subparser.add_argument(
    "--target", help="ip, e.g., 239.255.255.250 or FF02::C to listen to"
)

args = parser.parse_args()
pprint_indent = 4 if args.pprint else None

event_handler = None


async def create_device(description_url: str) -> UpnpDevice:
    """Create UpnpDevice."""
    timeout = args.timeout
    requester = AiohttpRequester(timeout)
    disable_validation = not args.strict
    factory = UpnpFactory(
        requester, disable_state_variable_validation=disable_validation
    )
    return await factory.async_create_device(description_url)


def get_timestamp() -> Union[str, float]:
    """Timestamp depending on configuration."""
    if args.iso8601:
        return datetime.now().isoformat(" ")
    return time.time()


def bind_host_port() -> Tuple[str, int]:
    """Determine listening host/port."""
    bind = args.bind

    if not bind:
        # figure out listening host ourselves
        target_url = args.device
        parsed = urllib.parse.urlparse(target_url)
        target_host = parsed.hostname
        bind = get_local_ip(target_host)

    if ":" not in bind:
        bind = bind + ":" + str(DEFAULT_PORT)

    host, port = bind.split(":")
    return host, int(port)


def service_from_device(device: UpnpDevice, service_name: str) -> Optional[UpnpService]:
    """Get UpnpService from UpnpDevice by name or part or abbreviation."""
    for service in device.services.values():
        part = service.service_id.split(":")[-1]
        abbr = "".join([c for c in part if c.isupper()])
        if service_name in (service.service_type, part, abbr):
            return service

    return None


def on_event(
    service: UpnpService, service_variables: Sequence[UpnpStateVariable]
) -> None:
    """Handle a UPnP event."""
    _LOGGER.debug(
        "State variable change for %s, variables: %s",
        service,
        ",".join([sv.name for sv in service_variables]),
    )
    obj = {
        "timestamp": get_timestamp(),
        "service_id": service.service_id,
        "service_type": service.service_type,
        "state_variables": {sv.name: sv.value for sv in service_variables},
    }

    # special handling for DLNA LastChange state variable
    if len(service_variables) == 1 and service_variables[0].name == "LastChange":
        if not args.nolastchange:
            print(json.dumps(obj, indent=pprint_indent))
        last_change = service_variables[0]
        dlna_handle_notify_last_change(last_change)
    else:
        print(json.dumps(obj, indent=pprint_indent))


async def call_action(description_url: str, call_action_args: Sequence) -> None:
    """Call an action and show results."""
    device = await create_device(description_url)

    if "/" in call_action_args[0]:
        service_name, action_name = call_action_args[0].split("/")
    else:
        service_name = call_action_args[0]
        action_name = ""

    for action_arg in call_action_args[1:]:
        if "=" not in action_arg:
            print("Invalid argument value: %s" % (action_arg,))
            print("Use: Argument=value")
            sys.exit(1)

    action_args = {a.split("=", 1)[0]: a.split("=", 1)[1] for a in call_action_args[1:]}

    # get service
    service = service_from_device(device, service_name)
    if not service:
        print("Unknown service: %s" % (service_name,))
        print(
            "Available services:\n%s"
            % (
                "\n".join(
                    [
                        "  " + device_service.service_id.split(":")[-1]
                        for device_service in device.services.values()
                    ]
                )
            )
        )
        sys.exit(1)

    # get action
    if not service.has_action(action_name):
        print("Unknown action: %s" % (action_name,))
        print(
            "Available actions:\n%s"
            % ("\n".join(["  " + name for name in sorted(service.actions)]))
        )
        sys.exit(1)
    action = service.action(action_name)

    # get in variables
    coerced_args = {}
    for key, value in action_args.items():
        in_arg = action.argument(key)
        if not in_arg:
            print("Unknown argument: %s" % (key,))
            print(
                "Available arguments: %s"
                % (",".join([a.name for a in action.in_arguments()]))
            )
            sys.exit(1)
        coerced_args[key] = in_arg.coerce_python(value)

    # ensure all in variables given
    for in_arg in action.in_arguments():
        if in_arg.name not in action_args:
            print("Missing in-arguments")
            print(
                "Known in-arguments:\n%s"
                % (
                    "\n".join(
                        [
                            "  " + in_arg.name
                            for in_arg in sorted(
                                action.in_arguments(), key=operator.attrgetter("name")
                            )
                        ]
                    )
                )
            )
            sys.exit(1)

    _LOGGER.debug(
        "Calling %s.%s, parameters:\n%s",
        service.service_id,
        action.name,
        "\n".join(["%s:%s" % (key, value) for key, value in coerced_args.items()]),
    )
    result = await action.async_call(**coerced_args)

    _LOGGER.debug(
        "Results:\n%s",
        "\n".join(["%s:%s" % (key, value) for key, value in coerced_args.items()]),
    )

    obj = {
        "timestamp": get_timestamp(),
        "service_id": service.service_id,
        "service_type": service.service_type,
        "action": action.name,
        "in_parameters": coerced_args,
        "out_parameters": result,
    }
    print(json.dumps(obj, indent=pprint_indent))


async def subscribe(description_url: str, service_names: Any) -> None:
    """Subscribe to service(s) and output updates."""
    global event_handler  # pylint: disable=global-statement

    device = await create_device(description_url)

    # start notify server/event handler
    host, port = bind_host_port()
    server = AiohttpNotifyServer(device.requester, port, listen_host=host)
    await server.start_server()
    _LOGGER.debug("Listening on: %s", server.callback_url)

    # gather all wanted services
    if "*" in service_names:
        service_names = device.services.keys()

    services = []
    for service_name in service_names:
        service = service_from_device(device, service_name)
        if not service:
            print("Unknown service: %s" % (service_name,))
            sys.exit(1)
        service.on_event = on_event
        services.append(service)

    # subscribe to services
    event_handler = server.event_handler
    for service in services:
        await event_handler.async_subscribe(service)

    # keep the webservice running
    while True:
        await asyncio.sleep(120)
        await event_handler.async_resubscribe_all()


async def search(search_args: Any) -> None:
    """Discover devices."""
    timeout = args.timeout
    service_type = search_args.service_type
    source_ip = search_args.bind
    target_ip = search_args.target
    if sys.platform == "win32" and not source_ip:
        _LOGGER.debug('Running on win32 without --bind argument, forcing to "0.0.0.0"')
        source_ip = "0.0.0.0"  # force to IPv4 to prevent asyncio crash/WinError 10022
    if source_ip:
        source_ip = ip_address(source_ip)
    if target_ip:
        target_ip = ip_address(target_ip)

    async def on_response(data: Mapping[str, Any]) -> None:
        data = {key: str(value) for key, value in data.items()}
        print(json.dumps(data, indent=pprint_indent))

    await async_ssdp_search(
        service_type=service_type,
        source_ip=source_ip,
        target_ip=target_ip,
        timeout=timeout,
        async_callback=on_response,
    )


async def advertisements(advertisement_args: Any) -> None:
    """Listen for advertisements."""
    source_ip = advertisement_args.bind
    target_ip = advertisement_args.target
    if sys.platform == "win32" and not source_ip:
        _LOGGER.debug('Running on win32 without --bind argument, forcing to "0.0.0.0"')
        source_ip = "0.0.0.0"  # force to IPv4 to prevent asyncio crash/WinError 10022
    if source_ip:
        source_ip = ip_address(source_ip)
    if target_ip:
        target_ip = ip_address(target_ip)

    async def on_notify(data: Mapping[str, Any]) -> None:
        data = {key: str(value) for key, value in data.items()}
        print(json.dumps(data, indent=pprint_indent))

    listener = UpnpAdvertisementListener(
        on_alive=on_notify,
        on_byebye=on_notify,
        on_update=on_notify,
        source_ip=source_ip,
        target_ip=target_ip,
    )
    await listener.async_start()
    try:
        while True:
            await asyncio.sleep(60)
    except KeyboardInterrupt:
        _LOGGER.debug("KeyboardInterrupt")
        await listener.async_stop()
        raise


async def async_main() -> None:
    """Async main."""
    if args.debug:
        _LOGGER.setLevel(logging.DEBUG)
        _LOGGER_LIB.setLevel(logging.DEBUG)
        _LOGGER_TRAFFIC.setLevel(logging.INFO)
    if args.debug_traffic:
        _LOGGER_TRAFFIC.setLevel(logging.DEBUG)

    if args.command == "call-action":
        await call_action(args.device, getattr(args, "call-action"))
    elif args.command == "subscribe":
        await subscribe(args.device, args.service)
    elif args.command == "search":
        await search(args)
    elif args.command == "advertisements":
        await advertisements(args)


def main() -> None:
    """Set up async loop and run the main program."""
    loop = asyncio.get_event_loop()

    try:
        loop.run_until_complete(async_main())
    except KeyboardInterrupt:
        if event_handler:
            loop.run_until_complete(event_handler.async_unsubscribe_all())
    finally:
        loop.close()


if __name__ == "__main__":
    main()
