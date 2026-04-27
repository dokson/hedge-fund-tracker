"""
Tests for scripts.docker_up port discovery.
"""

import socket
import unittest
from unittest.mock import patch

from scripts.docker_up import find_available_port


class TestFindAvailablePort(unittest.TestCase):
    """
    Verify that find_available_port detects free and busy ports correctly
    without binding to all network interfaces.
    """

    def test_returns_start_port_when_free(self):
        """
        When the starting port is free, it should be returned as-is.
        """
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.bind(("127.0.0.1", 0))
            free_port = probe.getsockname()[1]

        result = find_available_port(start=free_port, max_attempts=1)
        self.assertEqual(result, free_port)

    def test_skips_busy_port_and_returns_next_free(self):
        """
        When the starting port is occupied, the scan should advance to the next free port.
        """
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as busy:
            busy.bind(("127.0.0.1", 0))
            busy.listen(1)
            busy_port = busy.getsockname()[1]

            result = find_available_port(start=busy_port, max_attempts=20)
            self.assertNotEqual(result, busy_port)
            self.assertGreater(result, busy_port)
            self.assertLessEqual(result, busy_port + 19)

    def test_raises_when_no_port_available(self):
        """
        When every candidate in range is busy, a RuntimeError should be raised.
        """
        sockets: list[socket.socket] = []
        try:
            first = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            first.bind(("127.0.0.1", 0))
            first.listen(1)
            sockets.append(first)
            start = first.getsockname()[1]

            for offset in range(1, 5):
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                try:
                    s.bind(("127.0.0.1", start + offset))
                    s.listen(1)
                    sockets.append(s)
                except OSError:
                    s.close()
                    self.skipTest(f"Could not occupy contiguous port {start + offset}")

            with self.assertRaises(RuntimeError):
                find_available_port(start=start, max_attempts=len(sockets))
        finally:
            for s in sockets:
                s.close()

    def test_does_not_leave_socket_bound_after_return(self):
        """
        After the probe returns, the discovered port must be re-bindable
        (i.e., the probe socket was properly closed via the context manager).
        """
        port = find_available_port(start=18000, max_attempts=50)
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", port))

    def test_skips_port_with_active_listener_via_connect_probe(self):
        """
        A port with an active listener (e.g. a Docker container publishing
        on the wildcard address) must be reported as busy by the connect
        probe and skipped, even when a fresh loopback bind would succeed.

        The connect probe is mocked so the test does not need to bind to
        any wildcard address itself.
        """
        busy_candidates = {19000}

        def fake_is_port_in_use(port: int) -> bool:
            """
            Simulate an external listener occupying a specific port.
            """
            return port in busy_candidates

        with patch("scripts.docker_up._is_port_in_use", side_effect=fake_is_port_in_use):
            result = find_available_port(start=19000, max_attempts=20)

        self.assertNotIn(result, busy_candidates)
        self.assertEqual(result, 19001)


if __name__ == "__main__":
    unittest.main()
