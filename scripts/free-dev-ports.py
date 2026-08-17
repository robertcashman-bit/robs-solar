#!/usr/bin/env python3
"""Stop leftover Rob's Finance listeners on the local Next and API ports.

``lsof -ti tcp:PORT`` misses IPv6 Next listeners on some Linux agents and can
also return Chrome client PIDs. This only signals processes that own a LISTEN
socket for the requested ports.
"""

from __future__ import annotations

import os
import signal
import sys
import time
from pathlib import Path

DEFAULT_PORTS = (8000, 3000)
LISTEN_STATE = "0A"


def _hex_port(port: int) -> str:
    return f"{port:04X}"


def listen_inodes(port: int) -> set[str]:
    wanted = _hex_port(port)
    found: set[str] = set()
    for path in (Path("/proc/net/tcp"), Path("/proc/net/tcp6")):
        try:
            lines = path.read_text().splitlines()[1:]
        except OSError:
            continue
        for line in lines:
            parts = line.split()
            if len(parts) < 10:
                continue
            local, state, inode = parts[1], parts[3], parts[9]
            if state != LISTEN_STATE:
                continue
            if local.rsplit(":", 1)[-1].upper() != wanted:
                continue
            found.add(inode)
    return found


def pids_for_inodes(inodes: set[str]) -> set[int]:
    if not inodes:
        return set()
    pids: set[int] = set()
    proc = Path("/proc")
    for entry in proc.iterdir():
        if not entry.name.isdigit():
            continue
        fd_dir = entry / "fd"
        try:
            for fd in fd_dir.iterdir():
                try:
                    target = os.readlink(fd)
                except OSError:
                    continue
                if target.startswith("socket:[") and target[8:-1] in inodes:
                    pids.add(int(entry.name))
                    break
        except OSError:
            continue
    return pids


def listener_pids(port: int) -> set[int]:
    return pids_for_inodes(listen_inodes(port))


def _signal(pid: int, sig: signal.Signals) -> None:
    if pid in {os.getpid(), os.getppid()}:
        return
    try:
        os.kill(pid, sig)
    except ProcessLookupError:
        return


def free_ports(ports: list[int]) -> list[tuple[int, int]]:
    stopped: list[tuple[int, int]] = []
    for port in ports:
        for pid in sorted(listener_pids(port)):
            _signal(pid, signal.SIGTERM)
            stopped.append((port, pid))
    time.sleep(0.4)
    for port in ports:
        for pid in sorted(listener_pids(port)):
            _signal(pid, signal.SIGKILL)
    return stopped


def self_test() -> int:
    if _hex_port(3000) != "0BB8":
        print("hex port mapping is wrong", file=sys.stderr)
        return 1
    if listen_inodes(59999):
        print("closed port 59999 unexpectedly has a LISTEN inode", file=sys.stderr)
        return 1
    print("free-dev-ports self-test ok")
    return 0


def main(argv: list[str]) -> int:
    if argv == ["--self-test"]:
        return self_test()
    ports = [int(item) for item in argv] if argv else list(DEFAULT_PORTS)
    for port, pid in free_ports(ports):
        print(f"stopped listener pid {pid} on :{port}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
