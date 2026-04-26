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


def find_available_port(start: int = 8000, max_attempts: int = 20) -> int:
    """
    Scan upward from `start` and return the first port that's free on the host.

    Tries to bind on 0.0.0.0 (the address Docker uses) so phantom reservations on
    127.0.0.1 don't get a false positive. Raises RuntimeError if nothing is free
    within `max_attempts` candidates.
    """
    for offset in range(max_attempts):
        candidate = start + offset
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind(("0.0.0.0", candidate))
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
