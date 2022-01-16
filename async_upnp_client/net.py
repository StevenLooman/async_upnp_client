# -*- coding: utf-8 -*-
"""Network related utils for async_upnp_client."""

import socket
import sys
from ipaddress import IPv4Address, IPv6Address, ip_address
from socket import AddressFamily  # pylint: disable=no-name-in-module
from typing import Optional, Union, cast
from urllib.parse import urljoin, urlparse, urlsplit, urlunsplit

from async_upnp_client.const import AddressTupleV4Type, AddressTupleV6Type, AddressTupleVXType, IPvXAddress

EXTERNAL_IP = "1.1.1.1"
EXTERNAL_IP_V6 = "2001::1"
EXTERNAL_PORT = 80


def absolute_url(device_url: str, url: str) -> str:
    """
    Convert a relative URL to an absolute URL pointing at device.

    If url is already an absolute url (i.e., starts with http:/https:),
    then the url itself is returned.
    """
    if url.startswith("http:") or url.startswith("https:"):
        return url

    return urljoin(device_url, url)


def get_local_ip(
    target_ip: Optional[IPvXAddress] = None, family: Optional[AddressFamily] = None
) -> str:
    """Try to get the local IP of this machine, used to talk to target_url or external world."""
    if target_ip is None:
        if family == socket.AF_INET:
            target_addr = (EXTERNAL_IP, 0)
        elif family == socket.AF_INET6:
            target_addr = (EXTERNAL_IP_V6, 0, 0, 0)  # XXX TODO: How to get scope_id?
        else:
            family = AddressFamily.AF_INET
            target_addr = (EXTERNAL_IP, 0)
    elif target_ip.version == 4:
        family = AddressFamily.AF_INET
        target_addr = (str(target_ip), 0)
    elif target_ip.version == 6:
        target_ip = cast(IPv6Address, target_ip)
        family = AddressFamily.AF_INET6
        try:
            scope_id = int(target_ip.scope_id)
        except:
            scope_id = 0
        target_addr = (str(target_ip), 0, 0, scope_id)

    try:
        sock = socket.socket(family, socket.SOCK_DGRAM)
        sock.connect(
            target_addr
        )  # Connecting using SOCK_DGRAM doesn't cause any network activity.
        local_ip: str = sock.getsockname()[0]
        return local_ip
    finally:
        sock.close()


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


def get_source_address_tuple(
    target: AddressTupleVXType,
    source: Union[AddressTupleVXType, IPvXAddress, None] = None,
) -> AddressTupleVXType:
    """Get source address tuple from address tuple/ip address, if given."""
    if isinstance(source, tuple):
        return source

    if isinstance(source, IPv4Address) and not source.is_unspecified:
        return (
            str(source),
            0,
        )

    if isinstance(source, IPv6Address) and not source.is_unspecified:
        source_str = str(source)
        scope_id_index = source_str.rfind("%")
        if scope_id_index != -1:
            source_str = source_str[:scope_id_index]
        scope_id = getattr(source, "scope_id", "0") or "0"
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
        target_ip_address = IPv4Address(target[0])
        return (
            get_local_ip(target_ip_address, socket.AF_INET),
            0,
        )

    if isinstance(target, tuple) and len(target) == 4:
        target = cast(AddressTupleV6Type, target)
        target_ip_address = IPv6Address(target[0])  # XXX TODO: scope_id
        return (
            get_local_ip(target_ip_address, socket.AF_INET6),
            0,
            0,
            target[3],
        )

    raise NotImplementedError()


def get_source_address_tuple_for_location(location) -> AddressTupleVXType:
    """Get the source address tuple for a given location."""
    parts = urlparse(location)
    target = (parts.hostname, 0, 0, 0) if ':' in parts.netloc else (parts.hostname, 0)
    return get_source_address_tuple(target)
