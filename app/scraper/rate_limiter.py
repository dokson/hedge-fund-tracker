import threading
import time
from collections.abc import Callable


class RateLimiter:
    """
    Thread-safe token-bucket rate limiter.

    Tokens refill at `rate` per second up to `capacity`. acquire() blocks
    until a token is available, then consumes one. Designed to coordinate
    parallel SEC EDGAR requests across a thread pool so the per-host
    budget (~10 req/s) is honored regardless of worker count.
    """

    def __init__(
        self,
        rate: float,
        capacity: float | None = None,
        time_fn: Callable[[], float] = time.monotonic,
        sleep_fn: Callable[[float], None] = time.sleep,
    ):
        """
        Initialize the limiter.

        Args:
            rate: tokens added per second.
            capacity: max tokens that can accumulate; defaults to `rate` (1s burst).
            time_fn: clock source — overridable for tests.
            sleep_fn: sleep function — overridable for tests.
        """
        if rate <= 0:
            raise ValueError("rate must be positive")
        self._rate = rate
        self._capacity = capacity if capacity is not None else rate
        self._tokens = float(self._capacity)
        self._time = time_fn
        self._sleep = sleep_fn
        self._last = time_fn()
        self._lock = threading.Lock()

    def acquire(self) -> None:
        """
        Block until one token is available, then consume it.
        """
        while True:
            with self._lock:
                now = self._time()
                elapsed = now - self._last
                if elapsed > 0:
                    self._tokens = min(self._capacity, self._tokens + elapsed * self._rate)
                    self._last = now
                if self._tokens >= 1:
                    self._tokens -= 1
                    return
                # Floor at 1ms: with very high `rate` or a backwards-jumping
                # mock clock, the computed wait can collapse to ~0 and turn
                # the retry loop into a CPU-bound spin.
                wait = max((1 - self._tokens) / self._rate, 0.001)
            self._sleep(wait)
