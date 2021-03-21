# -*- coding: utf-8 -*-
"""SSPD protocol handler."""

import email
import logging
import socket
import sys
from asyncio import BaseProtocol, BaseTransport, DatagramTransport
from asyncio.events import AbstractEventLoop
from datetime import datetime
from ipaddress import IPv4Address, IPv6Address, ip_address
from typing import Awaitable, Callable, MutableMapping, Optional, Tuple, Union, cast
from urllib.parse import urlsplit, urlunsplit

from async_upnp_client.utils import CaseInsensitiveDict

SSDP_PORT = 1900
SSDP_IP_V4 = "239.255.255.250"
SSDP_IP_V6 = "FF02::C"
SSDP_TARGET_V4 = (SSDP_IP_V4, SSDP_PORT)
SSDP_TARGET_V6 = (SSDP_IP_V6, SSDP_PORT)
SSDP_TARGET = SSDP_TARGET_V4
SSDP_ST_ALL = "ssdp:all"
SSDP_ST_ROOTDEVICE = "upnp:rootdevice"
SSDP_MX = 4

SSDP_ALIVE = "ssdp:alive"
SSDP_UPDATE = "ssdp:update"
SSDP_BYEBYE = "ssdp:byebye"


_LOGGER = logging.getLogger(__name__)
_LOGGER_TRAFFIC_SSDP = logging.getLogger("async_upnp_client.traffic.ssdp")

IPvXAddress = Union[IPv4Address, IPv6Address]
AddressTupleV4Type = Tuple[str, int]
AddressTupleV6Type = Tuple[str, int, int, int]
AddressTupleVXType = Union[AddressTupleV4Type, AddressTupleV6Type]


def get_host_string(addr: AddressTupleVXType) -> str:
    """Construct host string from address tuple."""
    if len(addr) >= 3:
        addr = cast(AddressTupleV6Type, addr)
        if addr[3]:
            return "{}%{}".format(addr[0], addr[3])
    return addr[0]


def get_host_port_string(addr: AddressTupleVXType) -> str:
    """Return a properly escaped host port pair."""
    host = get_host_string(addr)
    if ":" in host:
        return "[{}]:{}".format(host, addr[1])
    return "{}:{}".format(host, addr[1])


def get_adjusted_url(url: str, addr: AddressTupleVXType) -> str:
    """Adjust a url with correction for link local scope."""
    if len(addr) < 4:
        return url

    addr = cast(AddressTupleV6Type, addr)

    if not addr[3]:
        return url

    data = urlsplit(url)
    try:
        address = ip_address(data.hostname)
    except ValueError:
        return url

    if not address.is_link_local:
        return url

    netloc = "[{}%{}]".format(data.hostname, addr[3])
    if data.port:
        netloc += ":{}".format(data.port)
    return urlunsplit(data._replace(netloc=netloc))


def build_ssdp_search_packet(
    ssdp_target: AddressTupleVXType, ssdp_mx: int, ssdp_st: str
) -> bytes:
    """Construct a SSDP packet."""
    return (
        "M-SEARCH * HTTP/1.1\r\n"
        "HOST:{target}\r\n"
        'MAN:"ssdp:discover"\r\n'
        "MX:{mx}\r\n"
        "ST:{st}\r\n"
        "\r\n".format(
            target=get_host_port_string(ssdp_target), mx=ssdp_mx, st=ssdp_st
        ).encode()
    )


def is_valid_ssdp_packet(data: bytes) -> bool:
    """Check if data is a valid and decodable packet."""
    return (
        bool(data)
        and b"\n" in data
        and (
            data.startswith(b"NOTIFY * HTTP/1.1")
            or data.startswith(b"M-SEARCH * HTTP/1.1")
            or data.startswith(b"HTTP/1.1 200 OK")
        )
    )


def decode_ssdp_packet(
    data: bytes, addr: AddressTupleVXType
) -> Tuple[str, CaseInsensitiveDict]:
    """Decode a message."""
    lines = data.split(b"\n")

    # request_line
    request_line = lines[0].strip().decode()

    # parse headers
    header_lines = b"\n".join(lines[1:])
    email_headers = email.message_from_bytes(header_lines)
    headers = CaseInsensitiveDict(**dict(email_headers.items()))

    # adjust some headers
    if "location" in headers:
        headers["_location_original"] = headers["location"]
        headers["location"] = get_adjusted_url(headers["location"], addr)

    # own data
    headers["_timestamp"] = datetime.now()
    headers["_host"] = get_host_string(addr)
    headers["_port"] = addr[1]

    if "usn" in headers and "uuid:" in headers["usn"]:
        parts = str(headers["usn"]).split("::")
        headers["_udn"] = parts[0]

    return request_line, headers


class SsdpProtocol(BaseProtocol):
    """SSDP Protocol."""

    def __init__(
        self,
        loop: AbstractEventLoop,
        on_connect: Optional[Callable[[DatagramTransport], Awaitable]] = None,
        on_data: Optional[Callable[[str, MutableMapping[str, str]], Awaitable]] = None,
    ) -> None:
        """Initialize."""
        self.loop = loop
        self.on_connect = on_connect
        self.on_data = on_data

        self.on_con_lost = loop.create_future()
        self.transport: Optional[DatagramTransport] = None

    def connection_made(self, transport: BaseTransport) -> None:
        """Handle connection made."""
        self.transport = cast(DatagramTransport, transport)

        if self.on_connect:
            callback = self.on_connect(self.transport)
            self.loop.create_task(callback)

    def datagram_received(self, data: bytes, addr: AddressTupleVXType) -> None:
        """Handle a discovery-response."""
        _LOGGER_TRAFFIC_SSDP.debug("Received packet from %s: %s", addr, data)

        if is_valid_ssdp_packet(data) and self.on_data:
            request_line, headers = decode_ssdp_packet(data, addr)
            callback = self.on_data(request_line, headers)
            self.loop.create_task(callback)

    def error_received(self, exc: Exception) -> None:
        """Handle an error."""
        # pylint: disable=no-self-use
        _LOGGER.debug("Received error: %s", exc)

    def connection_lost(self, exc: Optional[Exception]) -> None:
        """Handle connection lost."""


def get_source_ip_from_target_ip(target_ip: IPvXAddress) -> IPvXAddress:
    """Deduce a bind ip address from a target address potentially including scope."""
    if isinstance(target_ip, IPv6Address):
        scope_id = getattr(target_ip, "scope_id", None)
        if scope_id:
            return IPv6Address("::%" + scope_id)
        return IPv6Address("::")
    return IPv4Address("0.0.0.0")


def get_ssdp_socket(
    source_ip: IPvXAddress, target_ip: IPvXAddress
) -> Tuple[socket.socket, AddressTupleVXType, AddressTupleVXType]:
    """Create a socket to listen on."""
    target = socket.getaddrinfo(
        str(target_ip), SSDP_PORT, type=socket.SOCK_DGRAM, proto=socket.IPPROTO_UDP
    )[0]
    source = socket.getaddrinfo(
        str(source_ip), 0, type=socket.SOCK_DGRAM, proto=socket.IPPROTO_UDP
    )[0]
    _LOGGER.debug("Creating socket on %s to %s", source, target)

    # create socket
    sock = socket.socket(source[0], source[1], source[2])
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    # multicast
    if target_ip.is_multicast:
        if source[0] == socket.AF_INET6:
            sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_MULTICAST_HOPS, 2)
            addr = cast(AddressTupleV6Type, source[4])
            if addr[3]:
                mreq = target_ip.packed + addr[3].to_bytes(4, sys.byteorder)
                sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_JOIN_GROUP, mreq)
                sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_MULTICAST_IF, addr[3])
            else:
                _LOGGER.debug("Skipping setting multicast interface")
        else:
            sock.setsockopt(socket.SOL_IP, socket.IP_MULTICAST_IF, source_ip.packed)
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
            sock.setsockopt(
                socket.IPPROTO_IP,
                socket.IP_ADD_MEMBERSHIP,
                target_ip.packed + source_ip.packed,
            )

    return sock, source[4], target[4]
