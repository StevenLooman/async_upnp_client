# -*- coding: utf-8 -*-
"""async_upnp_client.ssdp module."""

import logging
import socket
import sys
from asyncio import BaseTransport, DatagramProtocol, DatagramTransport
from asyncio.events import AbstractEventLoop
from datetime import datetime
from ipaddress import IPv4Address, IPv6Address, ip_address
from typing import Awaitable, Callable, Optional, Tuple, cast
from urllib.parse import urlsplit, urlunsplit

from aiohttp.http_exceptions import InvalidHeader
from aiohttp.http_parser import HeadersParser

from async_upnp_client.const import (
    AddressTupleV6Type,
    AddressTupleVXType,
    IPvXAddress,
    SsdpHeaders,
    UniqueDeviceName,
)
from async_upnp_client.exceptions import UpnpError
from async_upnp_client.utils import CaseInsensitiveDict

SSDP_PORT = 1900
SSDP_IP_V4 = "239.255.255.250"
SSDP_IP_V6_LINK_LOCAL = "FF02::C"
SSDP_IP_V6_SITE_LOCAL = "FF05::C"
SSDP_IP_V6_ORGANISATION_LOCAL = "FF08::C"
SSDP_IP_V6_GLOBAL = "FF0E::C"
SSDP_IP_V6 = SSDP_IP_V6_LINK_LOCAL
SSDP_TARGET_V4 = (SSDP_IP_V4, SSDP_PORT)
SSDP_TARGET_V6 = (
    SSDP_IP_V6,
    SSDP_PORT,
    0,
    0,
)  # Replace the last item with your scope_id!
SSDP_TARGET = SSDP_TARGET_V4
SSDP_ST_ALL = "ssdp:all"
SSDP_ST_ROOTDEVICE = "upnp:rootdevice"
SSDP_MX = 4
SSDP_DISCOVER = '"ssdp:discover"'

_LOGGER = logging.getLogger(__name__)
_LOGGER_TRAFFIC_SSDP = logging.getLogger("async_upnp_client.traffic.ssdp")


def get_host_string(addr: AddressTupleVXType) -> str:
    """Construct host string from address tuple."""
    if len(addr) == 4:
        addr = cast(AddressTupleV6Type, addr)
        if addr[3]:
            return f"{addr[0]}%{addr[3]}"

    return addr[0]


def get_host_port_string(addr: AddressTupleVXType) -> str:
    """Return a properly escaped host port pair."""
    host = get_host_string(addr)
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


def is_ipv4_address(addr: AddressTupleVXType) -> bool:
    """Test if addr is a IPv4 tuple."""
    return len(addr) == 2


def is_ipv6_address(addr: AddressTupleVXType) -> bool:
    """Test if addr is a IPv6 tuple."""
    return len(addr) == 4


def build_ssdp_packet(status_line: str, headers: SsdpHeaders) -> bytes:
    """Construct a SSDP packet."""
    headers_str = "\r\n".join([f"{key}:{value}" for key, value in headers.items()])
    return f"{status_line}\r\n{headers_str}\r\n\r\n".encode()


def build_ssdp_search_packet(
    ssdp_target: AddressTupleVXType, ssdp_mx: int, ssdp_st: str
) -> bytes:
    """Construct a SSDP M-SEARCH packet."""
    request_line = "M-SEARCH * HTTP/1.1"
    headers = {
        "HOST": f"{get_host_port_string(ssdp_target)}",
        "MAN": '"ssdp:discover"',
        "MX": f"{ssdp_mx}",
        "ST": f"{ssdp_st}",
    }
    return build_ssdp_packet(request_line, headers)


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
    data: bytes,
    local_addr: Optional[AddressTupleVXType],
    remote_addr: AddressTupleVXType,
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
        headers["location"] = get_adjusted_url(headers["location"], remote_addr)

    # own data
    headers["_timestamp"] = datetime.now()
    headers["_host"] = get_host_string(remote_addr)
    headers["_port"] = remote_addr[1]
    headers["_local_addr"] = local_addr
    headers["_remote_addr"] = remote_addr

    udn = udn_from_headers(headers)
    if udn:
        headers["_udn"] = udn

    return request_line, headers


class SsdpProtocol(DatagramProtocol):
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
        assert self.transport

        if self.on_data and is_valid_ssdp_packet(data):
            sock: Optional[socket.socket] = self.transport.get_extra_info("socket")
            local_addr = sock.getsockname() if sock is not None else None
            try:
                request_line, headers = decode_ssdp_packet(data, local_addr, addr)
            except InvalidHeader as exc:
                _LOGGER.debug("Ignoring received packet with invalid headers: %s", exc)
                return

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
        _LOGGER.debug("Sending SSDP packet, transport: %s", self.transport)
        _LOGGER_TRAFFIC_SSDP.debug(
            "Sending SSDP packet, target: %s, data: %s", target, packet
        )
        assert self.transport is not None
        self.transport.sendto(packet, target)


def determine_source_target(
    source: Optional[AddressTupleVXType] = None,
    target: Optional[AddressTupleVXType] = None,
) -> Tuple[AddressTupleVXType, AddressTupleVXType]:
    """Determine source and target."""
    if source is None and target is None:
        return ("0.0.0.0", 0), (SSDP_IP_V4, SSDP_PORT)

    if source is not None and target is None:
        if len(source) == 2:
            return source, (SSDP_IP_V4, SSDP_PORT)

        source = cast(AddressTupleV6Type, source)
        return source, (SSDP_IP_V6, SSDP_PORT, 0, source[3])

    if source is None and target is not None:
        if len(target) == 2:
            return (
                "0.0.0.0",
                0,
            ), target

        target = cast(AddressTupleV6Type, target)
        return ("::", 0, 0, target[3]), target

    if source is not None and target is not None and len(source) != len(target):
        raise UpnpError("Source and target do not match protocol")

    return cast(AddressTupleVXType, source), cast(AddressTupleVXType, target)


def ip_port_from_address_tuple(
    address_tuple: AddressTupleVXType,
) -> Tuple[IPvXAddress, int]:
    """Get IPvXAddress from AddressTupleVXType."""
    if len(address_tuple) == 4:
        address_tuple = cast(AddressTupleV6Type, address_tuple)
        if "%" in address_tuple[0]:
            return IPv6Address(address_tuple[0]), address_tuple[1]

        return IPv6Address(f"{address_tuple[0]}%{address_tuple[3]}"), address_tuple[1]

    return IPv4Address(address_tuple[0]), address_tuple[1]


def get_ssdp_socket(
    source: AddressTupleVXType,
    target: AddressTupleVXType,
) -> Tuple[socket.socket, AddressTupleVXType, AddressTupleVXType]:
    """Create a socket to listen on."""
    target_ip, target_port = ip_port_from_address_tuple(target)
    target_info = socket.getaddrinfo(
        str(target_ip),
        target_port,
        type=socket.SOCK_DGRAM,
        proto=socket.IPPROTO_UDP,
    )[0]
    source_ip, source_port = ip_port_from_address_tuple(source)
    source_info = socket.getaddrinfo(
        str(source_ip), source_port, type=socket.SOCK_DGRAM, proto=socket.IPPROTO_UDP
    )[0]
    _LOGGER.debug("Creating socket, source: %s, target: %s", source_info, target_info)

    # create socket
    sock = socket.socket(source_info[0], source_info[1], source_info[2])
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

    # multicast
    if target_ip.is_multicast:
        if source_info[0] == socket.AF_INET6:
            sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_MULTICAST_HOPS, 2)
            addr = cast(AddressTupleV6Type, source_info[4])
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

    return sock, source_info[4], target_info[4]
