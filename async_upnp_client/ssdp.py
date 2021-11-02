# -*- coding: utf-8 -*-
"""SSPD protocol handler."""

import logging
import socket
import sys
from asyncio import BaseProtocol, BaseTransport, DatagramTransport
from asyncio.events import AbstractEventLoop
from datetime import datetime
from ipaddress import IPv4Address, IPv6Address, ip_address
from typing import Awaitable, Callable, Optional, Tuple, Union, cast
from urllib.parse import urlsplit, urlunsplit

from aiohttp.http_parser import HeadersParser

from async_upnp_client.const import (
    AddressTupleV4Type,
    AddressTupleV6Type,
    AddressTupleVXType,
    IPvXAddress,
    SsdpHeaders,
    UniqueDeviceName,
)
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
SSDP_DISCOVER = '"ssdp:discover"'

_LOGGER = logging.getLogger(__name__)
_LOGGER_TRAFFIC_SSDP = logging.getLogger("async_upnp_client.traffic.ssdp")


def ip_address_from_address_tuple(address_tuple: AddressTupleVXType) -> IPvXAddress:
    """Get IPvXAddress from AddressTupleVXType."""
    if len(address_tuple) == 4:
        address_tuple = cast(AddressTupleV6Type, address_tuple)
        min_ver = (
            3,
            9,
        )  # Python >=3.9 supports IPv6Address with scope_id
        if sys.version_info >= min_ver and address_tuple[3]:
            return IPv6Address(f"{address_tuple[0]}%{address_tuple[3]}")
        return IPv6Address(address_tuple[0])

    return IPv4Address(address_tuple[0])


def ip_address_str_from_address_tuple(address_tuple: AddressTupleVXType) -> str:
    """Get IP address as string from AddressTupleVXType."""
    # This function is mostly used to work around Python <3.9 IPv6Address not supporting scope_ids.
    if len(address_tuple) == 4:
        address_tuple = cast(AddressTupleV6Type, address_tuple)
        if "%" not in address_tuple[0] and address_tuple[3]:
            return f"{address_tuple[0]}%{address_tuple[3]}"

    return f"{address_tuple[0]}"


def get_source_address_tuple(
    target: AddressTupleVXType,
    source: Union[AddressTupleVXType, IPvXAddress, None] = None,
) -> AddressTupleVXType:
    """Get source address tuple from address tuple/ip address, if given."""
    if isinstance(source, tuple):
        return source

    if isinstance(source, IPv4Address):
        return (
            str(source),
            0,
        )

    if isinstance(source, IPv6Address):
        source_str = str(source)
        scope_id = getattr(source, "scope_id", "0") or "0"
        scope_id_index = source_str.rfind("%")
        if scope_id_index != -1:
            source_str = source_str[:scope_id_index]
        if scope_id.isdigit():
            scope_id = int(scope_id)
        return (
            source_str,
            0,
            0,
            cast(int, scope_id),
        )

    if isinstance(target, tuple) and len(target) == 2:
        target = cast(AddressTupleV4Type, target)
        return (
            "0.0.0.0",
            0,
        )

    if isinstance(target, tuple) and len(target) == 4:
        target = cast(AddressTupleV6Type, target)
        return (
            "::",
            0,
            0,
            target[3],
        )

    raise NotImplementedError()


def get_target_address_tuple(
    target: Union[AddressTupleVXType, IPvXAddress, None] = None,
    target_port: Optional[int] = None,
    source: Union[AddressTupleVXType, IPvXAddress, None] = None,
) -> AddressTupleVXType:
    """Get target address tuple."""
    # pylint: disable=too-many-return-statements
    if isinstance(target, tuple):
        return target

    if isinstance(target, IPv4Address):
        return (
            str(target),
            target_port or SSDP_PORT,
        )

    if isinstance(target, IPv6Address):
        target_str = str(target)
        scope_id = getattr(target, "scope_id", "0") or "0"
        scope_id_index = target_str.rfind("%")
        if scope_id_index != -1:
            target_str = target_str[:scope_id_index]
        if scope_id.isdigit():
            scope_id = int(scope_id)
        return (
            target_str,
            target_port or SSDP_PORT,
            0,
            cast(int, scope_id),
        )

    if (
        isinstance(source, IPv4Address)
        or isinstance(source, tuple)
        and len(source) == 2
    ):
        return (
            SSDP_IP_V4,
            target_port or SSDP_PORT,
        )

    if isinstance(source, IPv6Address):
        scope_id = getattr(source, "scope_id", "0") or "0"
        if scope_id.isdigit():
            scope_id = int(scope_id)
        return (
            SSDP_IP_V6,
            target_port or SSDP_PORT,
            0,
            cast(int, scope_id),
        )

    if isinstance(source, tuple) and len(source) == 4:
        source = cast(AddressTupleV6Type, source)
        return (
            SSDP_IP_V6,
            target_port or SSDP_PORT,
            0,
            source[3],
        )

    # Default to IPv4.
    return (
        SSDP_IP_V4,
        target_port or SSDP_PORT,
    )


def get_host_string(addr: AddressTupleVXType) -> str:
    """Construct host string from address tuple."""
    if len(addr) == 4:
        addr = cast(AddressTupleV6Type, addr)
        if addr[3]:
            return f"{addr[0]}%{addr[3]}"
    return addr[0]


def get_host_port_string(addr: AddressTupleVXType) -> str:
    """Return a properly escaped host port pair."""
    host = addr[0]
    if ":" in host:
        return f"[{host}]:{addr[1]}"
    return f"{host}:{addr[1]}"


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

    netloc = f"[{data.hostname}%{addr[3]}]"
    if data.port:
        netloc += f":{data.port}"
    return urlunsplit(data._replace(netloc=netloc))


def build_ssdp_search_packet(
    ssdp_target: AddressTupleVXType, ssdp_mx: int, ssdp_st: str
) -> bytes:
    """Construct a SSDP packet."""
    return (
        f"M-SEARCH * HTTP/1.1\r\n"
        f"HOST:{get_host_port_string(ssdp_target)}\r\n"
        f'MAN:"ssdp:discover"\r\n'
        f"MX:{ssdp_mx}\r\n"
        f"ST:{ssdp_st}\r\n"
        f"\r\n"
    ).encode()


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


def udn_from_headers(headers: SsdpHeaders) -> Optional[UniqueDeviceName]:
    """Get UDN from USN in headers."""
    usn = headers.get("usn", "")
    if usn and usn.startswith("uuid:"):
        parts = str(usn).split("::")
        return parts[0]

    return None


def decode_ssdp_packet(
    data: bytes, addr: AddressTupleVXType
) -> Tuple[str, CaseInsensitiveDict]:
    """Decode a message."""
    lines = data.replace(b"\r\n", b"\n").split(b"\n")

    # request_line
    request_line = lines[0].strip().decode()

    if lines and lines[-1] != b"":
        lines.append(b"")

    parsed_headers, _ = HeadersParser().parse_headers(lines)
    headers = CaseInsensitiveDict(parsed_headers)

    # adjust some headers
    if "location" in headers:
        headers["_location_original"] = headers["location"]
        headers["location"] = get_adjusted_url(headers["location"], addr)

    # own data
    headers["_timestamp"] = datetime.now()
    headers["_host"] = get_host_string(addr)
    headers["_port"] = addr[1]

    udn = udn_from_headers(headers)
    if udn:
        headers["_udn"] = udn

    return request_line, headers


class SsdpProtocol(BaseProtocol):
    """SSDP Protocol."""

    def __init__(
        self,
        loop: AbstractEventLoop,
        on_connect: Optional[Callable[[DatagramTransport], Awaitable]] = None,
        on_data: Optional[Callable[[str, SsdpHeaders], Awaitable]] = None,
    ) -> None:
        """Initialize."""
        self.loop = loop
        self.on_connect = on_connect
        self.on_data = on_data

        self.on_con_lost = loop.create_future()
        self.transport: Optional[DatagramTransport] = None

    def connection_made(self, transport: BaseTransport) -> None:
        """Handle connection made."""
        _LOGGER.debug("Connection made, transport: %s", transport)
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
        _LOGGER.error("Received error: %s, transport: %s", exc, self.transport)

    def connection_lost(self, exc: Optional[Exception]) -> None:
        """Handle connection lost."""
        _LOGGER.debug("Lost connection, error: %s, transport: %s", exc, self.transport)

    def send_ssdp_packet(self, packet: bytes, target: AddressTupleVXType) -> None:
        """Send a SSDP packet."""
        _LOGGER.debug("Sending M-SEARCH packet, transport: %s", self.transport)
        _LOGGER_TRAFFIC_SSDP.debug("Sending M-SEARCH packet: %s", packet)
        assert self.transport is not None
        self.transport.sendto(packet, target)


def get_ssdp_socket(
    source: AddressTupleVXType, target: AddressTupleVXType
) -> Tuple[socket.socket, AddressTupleVXType, AddressTupleVXType]:
    """Create a socket to listen on."""
    target_ip_str = ip_address_str_from_address_tuple(target)
    target_addrinfo = socket.getaddrinfo(
        target_ip_str,
        target[1],
        type=socket.SOCK_DGRAM,
        proto=socket.IPPROTO_UDP,
    )[0]
    source_ip_str = ip_address_str_from_address_tuple(source)
    source_addrinfo = socket.getaddrinfo(
        source_ip_str, source[1], type=socket.SOCK_DGRAM, proto=socket.IPPROTO_UDP
    )[0]
    _LOGGER.debug("Creating socket on %s to %s", source, target_addrinfo)

    # create socket
    sock = socket.socket(source_addrinfo[0], source_addrinfo[1], source_addrinfo[2])
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

    # multicast
    target_ip = ip_address_from_address_tuple(target_addrinfo[4])
    if target_ip.is_multicast:
        source_ip = ip_address_from_address_tuple(source)
        if source_addrinfo[0] == socket.AF_INET6:
            sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_MULTICAST_HOPS, 2)
            addr = cast(AddressTupleV6Type, source_addrinfo[4])
            if addr[3]:
                mreq = target_ip.packed + addr[3].to_bytes(4, sys.byteorder)
                sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_JOIN_GROUP, mreq)
                sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_MULTICAST_IF, addr[3])
            else:
                _LOGGER.debug("Skipping setting multicast interface")
        else:
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF, source_ip.packed)
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
            sock.setsockopt(
                socket.IPPROTO_IP,
                socket.IP_ADD_MEMBERSHIP,
                target_ip.packed + source_ip.packed,
            )

    return sock, source_addrinfo[4], target_addrinfo[4]
