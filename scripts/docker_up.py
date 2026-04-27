"""
Wrapper around `docker compose up` that auto-discovers the first available host port
starting from 8000 (mirroring the Python local server behavior).

Sets HOST_PORT in the environment before launching compose so that the
${HOST_PORT:-8000}:8000 mapping in docker-compose.yml resolves to a free port.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys


def _is_port_in_use(port: int) -> bool:
    """
    Return True if `port` is currently held by a listener on the host.

    Uses a connect probe against the loopback address: if a TCP handshake
    completes, something is listening (covers wildcard 0.0.0.0 binds, which
    a loopback bind probe alone cannot detect on Windows).
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.1)
        return s.connect_ex(("127.0.0.1", port)) == 0


def find_available_port(start: int = 8000, max_attempts: int = 20) -> int:
    """
    Scan upward from `start` and return the first port that's free on the host.

    Combines two probes without exposing a socket on all interfaces:
      1. A connect probe to detect any active listener (including services
         bound to 0.0.0.0 by Docker on other platforms).
      2. A loopback bind probe to confirm the kernel will accept a fresh
         listener on the candidate port.

    Raises RuntimeError if nothing is free within `max_attempts` candidates.
    """
    for offset in range(max_attempts):
        candidate = start + offset
        if _is_port_in_use(candidate):
            continue
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", candidate))
                return candidate
            except OSError:
                continue
    raise RuntimeError(f"No available port found in range {start}-{start + max_attempts - 1}")


def main() -> int:
    """
    Resolve the first free port and exec `docker compose up` with HOST_PORT set.
    Extra CLI arguments are forwarded verbatim (e.g. `--build`, `-d`).
    """
    port = find_available_port()
    env = os.environ.copy()
    env["HOST_PORT"] = str(port)
    print(f"🚀 Starting docker compose with HOST_PORT={port} -> http://localhost:{port}", flush=True)
    cmd = ["docker", "compose", "up", *sys.argv[1:]]
    return subprocess.call(cmd, env=env, shell=(os.name == "nt"))


if __name__ == "__main__":
    raise SystemExit(main())
