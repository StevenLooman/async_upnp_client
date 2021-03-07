#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import socket
import struct

SSDP_TARGET = ("239.255.255.250", 1900)


def main():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    # sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 4)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    mreq = struct.pack("4sl", socket.inet_aton(SSDP_TARGET[0]), socket.INADDR_ANY)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)

    sock.bind(SSDP_TARGET)

    while True:
        (data, src) = sock.recvfrom(1024)
        print(data, src)


if __name__ == "__main__":
    main()
