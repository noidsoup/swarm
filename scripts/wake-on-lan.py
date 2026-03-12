#!/usr/bin/env python3
"""Send a Wake-on-LAN magic packet to power on the Windows machine remotely.

Usage (from Mac):
    python3 scripts/wake-on-lan.py AA:BB:CC:DD:EE:FF
    python3 scripts/wake-on-lan.py AA:BB:CC:DD:EE:FF --ip 192.168.1.255

Prerequisites:
    - Enable WoL in BIOS (usually under Power Management or Network Boot)
    - Enable WoL in Windows: Device Manager > Network Adapter > Properties >
      Power Management > "Allow this device to wake the computer"
    - Enable "Wake on Magic Packet" in Advanced adapter settings
"""

from __future__ import annotations

import argparse
import socket
import struct
import sys


def send_wol(mac: str, ip: str = "255.255.255.255", port: int = 9) -> None:
    mac_bytes = bytes.fromhex(mac.replace(":", "").replace("-", ""))
    if len(mac_bytes) != 6:
        print(f"Invalid MAC address: {mac}")
        sys.exit(1)

    magic = b"\xff" * 6 + mac_bytes * 16

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.sendto(magic, (ip, port))

    print(f"Wake-on-LAN packet sent to {mac} via {ip}:{port}")


def main():
    parser = argparse.ArgumentParser(description="Send Wake-on-LAN magic packet")
    parser.add_argument("mac", help="MAC address (AA:BB:CC:DD:EE:FF)")
    parser.add_argument("--ip", default="255.255.255.255",
                        help="Broadcast IP (default: 255.255.255.255)")
    parser.add_argument("--port", type=int, default=9,
                        help="UDP port (default: 9)")
    args = parser.parse_args()
    send_wol(args.mac, args.ip, args.port)


if __name__ == "__main__":
    main()
