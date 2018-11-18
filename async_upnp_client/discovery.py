# -*- coding: utf-8 -*-
"""UPnP discovery via Simple Service Discovery Protocol (SSDP)."""
import asyncio
import logging
import socket

from datetime import datetime
from ipaddress import IPv4Address


_LOGGER = logging.getLogger(__name__)
_LOGGER_TRAFFIC = logging.getLogger("async_upnp_client.traffic")

SSDP_TARGET = ('239.255.255.250', 1900)
SSDP_ST_ALL = 'ssdp:all'
SSDP_ST_ROOTDEVICE = 'upnp:rootdevice'
SSDP_MX = 4
RECV_SIZE = 32678


def _discovery_message(ssdp_target: str, ssdp_mx: int, ssdp_st: str):
    """Construct a SSDP packet."""
    return 'M-SEARCH * HTTP/1.1\r\n' \
           'HOST:{target}:{port}\r\n' \
           'MAN:"ssdp:discover"\r\n' \
           'MX:{mx}\r\n' \
           'ST:{st}\r\n' \
           '\r\n'.format(target=ssdp_target[0], port=ssdp_target[1],
                         mx=ssdp_mx, st=ssdp_st).encode()


def _parse_response(data):
    headers = {}
    for line in data.splitlines():
        decoded = line.decode()
        if ':' in decoded:
            key, value = decoded.split(':', 1)
            key = key.strip().lower()
            headers[key] = value.strip()

    # custom data
    headers['_timestamp'] = datetime.now()
    return headers


def discover(timeout: int = SSDP_MX,
             service_type: str = SSDP_ST_ALL,
             source_ip: IPv4Address = None):
    """Discover devices via SSDP."""
    # create socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, timeout)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.settimeout(timeout)
    if source_ip:
        sock.bind((source_ip, 0))

    # send discovery packet
    message = _discovery_message(SSDP_TARGET, timeout, service_type)
    _LOGGER.debug('Sending discovery message')
    _LOGGER_TRAFFIC.debug('Sending message:\n%s', message)
    sock.sendto(message, SSDP_TARGET)

    # handle replies
    responses = []
    try:
        while True:
            # parse response
            data, _ = sock.recvfrom(RECV_SIZE)
            _LOGGER_TRAFFIC.debug('Received packet:\n%s', data)

            response = _parse_response(data)
            _LOGGER.debug('Received response: %s', response)

            if response not in responses:
                responses.append(response)
    except socket.timeout:
        pass

    sock.close()
    return responses


async def async_discover(timeout: int = SSDP_MX,
                         service_type: str = SSDP_ST_ALL,
                         source_ip: IPv4Address = None,
                         async_callback=None,
                         loop=None):
    """Discover devices via SSDP."""
    loop = loop or asyncio.get_event_loop()

    # create socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, timeout)
    # sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    if source_ip:
        sock.bind((source_ip, 0))

    # create protocol and send discovery packet
    connect = loop.create_datagram_endpoint(
        lambda: SsdpDiscoveryProtocol(loop, timeout, service_type, async_callback),
        sock=sock,
    )
    transport, protocol = await connect

    # wait for devices to respond
    await asyncio.sleep(timeout)

    transport.close()

    return protocol.responses


class SsdpDiscoveryProtocol:
    """SSDP Discovery Protocol."""

    def __init__(self, loop, timeout, service_type, async_callback):
        """Initializer."""
        self.loop = loop
        self.timeout = timeout
        self.service_type = service_type
        self.async_callback = async_callback

        self.on_con_lost = loop.create_future()
        self.transport = None
        self.responses = []

    def connection_made(self, transport):
        """Handle connection made."""
        self.transport = transport

        message = _discovery_message(SSDP_TARGET, self.timeout, self.service_type)
        self.transport.sendto(message, SSDP_TARGET)

    def datagram_received(self, data, addr):
        """Handle a discovery-response."""
        _LOGGER_TRAFFIC.debug('Received packet from %s:\n%s', addr, data)

        response = _parse_response(data)
        _LOGGER.debug('Received response: %s', response)

        if response not in self.responses:
            self.responses.append(response)

            if self.async_callback:
                callback = self.async_callback(response)
                self.loop.create_task(callback)

    def error_received(self, exc):
        """Handle an error."""
        # pylint: disable=no-self-use
        _LOGGER.error('Received error: %s', exc)

    def connection_lost(self, exc):
        """Handle connection lost."""
        pass
