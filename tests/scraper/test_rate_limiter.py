import threading
import time as real_time
import unittest

from app.scraper.rate_limiter import RateLimiter


class _FakeClock:
    """
    Deterministic clock for rate-limiter tests.

    sleep() advances the clock instead of really sleeping, so token-bucket
    refill math can be asserted without flaky real-time timing.
    """

    def __init__(self):
        self.t = 0.0
        self.sleeps: list[float] = []

    def time(self):
        return self.t

    def sleep(self, s):
        self.sleeps.append(s)
        self.t += s


class TestRateLimiter(unittest.TestCase):
    def test_burst_within_capacity_does_not_sleep(self):
        """
        Initial burst up to capacity must be served instantly.
        """
        clk = _FakeClock()
        rl = RateLimiter(rate=10, capacity=10, time_fn=clk.time, sleep_fn=clk.sleep)
        for _ in range(10):
            rl.acquire()
        self.assertEqual(clk.sleeps, [])

    def test_request_beyond_capacity_waits_for_refill(self):
        """
        With capacity=1, the second acquire must wait 1/rate seconds.
        """
        clk = _FakeClock()
        rl = RateLimiter(rate=10, capacity=1, time_fn=clk.time, sleep_fn=clk.sleep)
        rl.acquire()
        rl.acquire()
        self.assertEqual(len(clk.sleeps), 1)
        self.assertAlmostEqual(clk.sleeps[0], 0.1, places=6)

    def test_tokens_refill_over_elapsed_time(self):
        """
        After the bucket drains, elapsed time refills tokens proportionally to rate.
        """
        clk = _FakeClock()
        rl = RateLimiter(rate=10, capacity=2, time_fn=clk.time, sleep_fn=clk.sleep)
        rl.acquire()
        rl.acquire()
        clk.t = 0.2  # +0.2s * 10/s = +2 tokens
        rl.acquire()
        rl.acquire()
        self.assertEqual(clk.sleeps, [])

    def test_concurrent_threads_serialize_safely(self):
        """
        Many threads sharing one limiter never crash and stay within capacity for an initial burst.
        """
        rl = RateLimiter(rate=1000, capacity=100)
        results: list[None] = []
        results_lock = threading.Lock()

        def worker():
            for _ in range(25):
                rl.acquire()
                with results_lock:
                    results.append(None)

        threads = [threading.Thread(target=worker) for _ in range(4)]
        start = real_time.monotonic()
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        elapsed = real_time.monotonic() - start

        self.assertEqual(len(results), 100)
        # 100 acquires fit in initial capacity; should be near-instant.
        self.assertLess(elapsed, 1.0)


if __name__ == "__main__":
    unittest.main()
