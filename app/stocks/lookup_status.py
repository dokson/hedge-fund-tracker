"""
Whether a price lookup heard back from every provider it asked.

A lookup that comes back empty means "no price" only when every provider
answered. If one was blocked, timed out or rate-limited, the price may well
exist: callers that remember misses (``app.backtest.price_cache``) must not
record that one. Providers report such failures with ``note_provider_failure``;
a caller wraps the lookup in ``tracking`` and reads ``failed`` afterwards. The
state is context-local, so concurrent lookups never see each other's failures.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass

__all__ = ["LookupStatus", "note_provider_failure", "tracking"]


@dataclass
class LookupStatus:
    """
    The outcome of one tracked lookup: ``failed`` once any provider could not answer.
    """

    failed: bool = False


_current: ContextVar[LookupStatus | None] = ContextVar("price_lookup_status", default=None)


def note_provider_failure() -> None:
    """
    Mark the tracked lookup in progress, if any, as not answered by every provider.
    """
    status = _current.get()
    if status is not None:
        status.failed = True


@contextmanager
def tracking() -> Iterator[LookupStatus]:
    """
    Track the provider failures of the lookups run inside the block.
    """
    status = LookupStatus()
    token = _current.set(status)
    try:
        yield status
    finally:
        _current.reset(token)
