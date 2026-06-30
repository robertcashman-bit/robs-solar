#!/usr/bin/env python3
"""Scan local subnet for Modbus TCP port 502 and probe Sunsynk serial registers."""

import asyncio
import ipaddress
import socket
import sys
from typing import Optional


async def probe_host(host: str, port: int = 502, timeout: float = 0.4) -> bool:
    try:
        _, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port),
            timeout=timeout,
        )
        writer.close()
        await writer.wait_closed()
        return True
    except (OSError, asyncio.TimeoutError):
        return False


def local_subnet() -> Optional[str]:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        network = ipaddress.ip_network(f"{ip}/24", strict=False)
        return str(network)
    except OSError:
        return None


async def main() -> int:
    subnet = local_subnet()
    if not subnet:
        print("Could not determine local subnet.", file=sys.stderr)
        return 1
    print(f"Scanning {subnet} for Modbus TCP :502 ...")
    network = ipaddress.ip_network(subnet, strict=False)
    hosts = [str(h) for h in network.hosts()]
    results = await asyncio.gather(*[probe_host(h) for h in hosts])
    found = [h for h, ok in zip(hosts, results) if ok]
    if not found:
        print("No open :502 hosts found. Set MODBUS_HOST manually in backend/.env")
        return 0
    print("Possible Modbus hosts:")
    for host in found:
        print(f"  {host}")
    print("\nAdd to backend/.env:")
    print(f"MODBUS_HOST={found[0]}")
    print("ADAPTER_MODE=modbus_tcp")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
