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
from typing import Optional

from async_upnp_client import UpnpDevice
from async_upnp_client import UpnpFactory
from async_upnp_client import UpnpService
from async_upnp_client.aiohttp import AiohttpRequester
from async_upnp_client.aiohttp import AiohttpNotifyServer
from async_upnp_client.aiohttp import get_local_ip
from async_upnp_client.dlna import dlna_handle_notify_last_change


logging.basicConfig()
_LOGGER = logging.getLogger('upnp-client')
_LOGGER.setLevel(logging.ERROR)
_LOGGER_LIB = logging.getLogger('async_upnp_client')
_LOGGER_LIB.setLevel(logging.ERROR)
_LOGGER_TRAFFIC = logging.getLogger('async_upnp_client.traffic')
_LOGGER_TRAFFIC.setLevel(logging.ERROR)

DEFAULT_PORT = 11302


parser = argparse.ArgumentParser(description='upnp_client')
parser.add_argument('--device', required=True, help='URL to device description XML')
parser.add_argument('--debug', action='store_true', help='Show debug messages')
parser.add_argument('--debug-traffic', action='store_true', help='Show network traffic')
parser.add_argument('--pprint', action='store_true', help='Pretty-print (indent) JSON output')

subparsers = parser.add_subparsers(title='Subcommands')
subparser = subparsers.add_parser('call-action', help='Call an action')
subparser.add_argument('call-action', nargs='+', help='service/action param1=val1 param2=val2')
subparser = subparsers.add_parser('subscribe', help='Subscribe to services')
subparser.add_argument('service', nargs='+', help='service type or part or abbreviation')
subparser.add_argument('--bind', help='ip[:port], e.g., 192.168.0.10:8090')

args = parser.parse_args()
pprint_indent = 4 if args.pprint else None

event_handler = None


def bind_host_port():
    """Determine listening host/port."""
    bind = args.bind

    if not bind:
        # figure out listening host ourselves
        target_url = args.device
        parsed = urllib.parse.urlparse(target_url)
        target_host = parsed.hostname
        bind = get_local_ip(target_host)

    if ':' not in bind:
        bind = bind + ':' + str(DEFAULT_PORT)
    return bind.split(':')


def service_from_device(device: UpnpDevice, service_name: str) -> Optional[UpnpService]:
    """Get UpnpService from UpnpDevice by name or part or abbreviation."""
    for service in device.services.values():
        part = service.service_id.split(':')[-1]
        abbr = ''.join([c for c in part if c.isupper()])
        if service_name in (service.service_type, part, abbr):
            return service
    return None


def on_event(service, service_variables):
    """Handle a UPnP event."""
    _LOGGER.debug('State variable change for %s, variables: %s',
                  service,
                  ','.join([sv.name for sv in service_variables]))
    obj = {
        'timestamp': time.time(),
        'service_id': service.service_id,
        'service_type': service.service_type,
        'state_variables': {sv.name: sv.value for sv in service_variables},
    }
    print(json.dumps(obj, indent=pprint_indent))

    # do some additional handling for DLNA LastChange state variable
    if len(service_variables) == 1 and \
       service_variables[0].name == 'LastChange':
        last_change = service_variables[0]
        dlna_handle_notify_last_change(last_change)


async def call_action(device: UpnpDevice, call_action_args):
    """Call an action and show results."""
    if '/' in call_action_args[0]:
        service_name, action_name = call_action_args[0].split('/')
    else:
        service_name = call_action_args[0]
        action_name = ''
    action_args = {a.split('=', 1)[0]: a.split('=', 1)[1] for a in call_action_args[1:]}

    # get service
    service = service_from_device(device, service_name)
    if not service:
        print('Unknown service: %s' % (service_name, ))
        print('Available services:\n%s' % (
            '\n'.join(['  ' + service.service_id.split(':')[-1]
                       for service in device.services.values()])
        ))
        sys.exit(1)

    # get action
    action = service.action(action_name)
    if not action:
        print('Available actions:\n%s' % (
            '\n'.join(['  ' + name for name in sorted(service.actions)])
        ))
        sys.exit(1)

    # get in variables
    coerced_args = {}
    for key, value in action_args.items():
        in_arg = action.argument(key)
        if not in_arg:
            print('Unknown argument: %s', (key, ))
            print('Available arguments: %s' % (
                ','.join([a.name for a in action.in_arguments()])))
            sys.exit(1)
        coerced_args[key] = in_arg.coerce_python(value)

    # ensure all in variables given
    for in_arg in action.in_arguments():
        if in_arg.name not in action_args:
            print('Missing in-arguments')
            print('Known in-arguments:\n%s' % (
                '\n'.join(['  ' + in_arg.name
                           for in_arg in sorted(action.in_arguments(),
                                                key=operator.attrgetter('name'))])
            ))
            sys.exit(1)

    _LOGGER.debug('Calling %s.%s, parameters:\n%s',
                  service.service_id, action.name,
                  '\n'.join(['%s:%s' % (key, value) for key, value in coerced_args.items()]))
    result = await action.async_call(**coerced_args)

    _LOGGER.debug('Results:\n%s',
                  '\n'.join(['%s:%s' % (key, value) for key, value in coerced_args.items()]))

    obj = {
        'timestamp': time.time(),
        'service_id': service.service_id,
        'service_type': service.service_type,
        'action': action.name,
        'in_parameters': coerced_args,
        'out_parameters': result,
    }
    print(json.dumps(obj, indent=pprint_indent))


async def subscribe(device: UpnpDevice, subscribe_args):
    """Subscribe to service(s) and output updates."""
    global event_handler  # pylint: disable=global-statement

    # start notify server/event handler
    host, port = bind_host_port()
    server = AiohttpNotifyServer(device.requester, port, listen_host=host)
    await server.start_server()
    _LOGGER.debug('Listening on: %s', server.callback_url)

    # gather all wanted services
    services = []
    for service_name in subscribe_args:
        if service_name == '*':
            services += device.services.values()
            continue

        service = service_from_device(device, service_name)
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


async def async_main():
    """Asunc main."""
    if args.debug:
        _LOGGER.setLevel(logging.DEBUG)
        _LOGGER_LIB.setLevel(logging.DEBUG)
    if args.debug_traffic:
        _LOGGER_TRAFFIC.setLevel(logging.DEBUG)

    requester = AiohttpRequester()
    factory = UpnpFactory(requester)
    device = await factory.async_create_device(args.device)

    if hasattr(args, 'call-action'):
        await call_action(device, getattr(args, 'call-action'))
    elif hasattr(args, 'service'):
        await subscribe(device, args.service)
    else:
        parser.print_usage()


def main():
    """Main."""
    loop = asyncio.get_event_loop()

    try:
        loop.run_until_complete(async_main())
    except KeyboardInterrupt:
        if event_handler:
            loop.run_until_complete(event_handler.async_unsubscribe_all())
    finally:
        loop.close()


if __name__ == '__main__':
    main()
