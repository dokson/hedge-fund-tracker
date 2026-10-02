"""
Per-file locks for the CSV database: an in-process lock per path, then a
sibling ``<name>.lock`` file so separate processes serialize too.
"""

import os
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from pathlib import Path

__all__ = ["file_lock", "held_thread_lock", "lock_file", "thread_lock_for"]

_path_thread_locks: dict[str, threading.Lock] = {}
_path_thread_locks_guard = threading.Lock()


def thread_lock_for(path: Path) -> threading.Lock:
    """
    Returns the in-process lock dedicated to ``path``, creating it on first use.
    """
    key = os.path.normcase(str(path.resolve()))
    with _path_thread_locks_guard:
        return _path_thread_locks.setdefault(key, threading.Lock())


@contextmanager
def held_thread_lock(lock: threading.Lock, timeout: float, name: str) -> Iterator[None]:
    """
    Holds ``lock`` for the block, raising TimeoutError if it is not acquired within
    ``timeout`` seconds (the lock is not reentrant, so a nested acquire would hang).
    """
    if not lock.acquire(timeout=timeout):
        raise TimeoutError(f"Could not acquire the in-process lock for {name} within {timeout} seconds.")
    try:
        yield
    finally:
        lock.release()


@contextmanager
def file_lock(path: str | Path, timeout: float = 30) -> Iterator[None]:
    """
    Synchronize read-modify-write access to any database file (non_quarterly.csv,
    a quarter's fund CSV, ...) the same way ``stocks_lock`` guards stocks.csv:
    a per-path in-process lock, then a sibling ``<name>.lock`` file across processes.
    """
    target = Path(path)
    with held_thread_lock(thread_lock_for(target), timeout, target.name), lock_file(target, timeout):
        yield


@contextmanager
def lock_file(target: Path, timeout: float) -> Iterator[None]:
    """
    Holds ``<target>.lock`` (O_CREAT|O_EXCL with bounded retry) for the duration
    of the block, reclaiming a stale lock left behind by a dead owner.
    """
    lock_path = target.with_name(f"{target.name}.lock")
    start_time = time.time()
    acquired_file = False

    try:
        while True:
            try:
                fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.close(fd)
                acquired_file = True
                break
            except FileExistsError as exc:
                if time.time() - start_time > timeout:
                    raise TimeoutError(
                        f"Could not acquire lock for {target.name} within {timeout} seconds."
                    ) from exc

                # Reclaim a stale lock that outlived its owner (>60s).
                # Rename before deleting: the rename is atomic, so when
                # several contenders reclaim at once only one wins and a
                # lock just re-acquired by a third party can't be deleted.
                try:
                    if time.time() - lock_path.stat().st_mtime > 60:
                        stale_path = lock_path.with_name(f"{lock_path.name}.stale-{os.getpid()}")
                        try:
                            lock_path.rename(stale_path)
                            stale_path.unlink()
                            continue
                        except OSError:
                            pass
                except OSError:
                    pass

                time.sleep(0.05)
            except OSError as exc:
                # Windows hot path: unlink of a held-open lock file raises
                # PermissionError on the next O_CREAT|O_EXCL. Retry, but
                # honor the timeout — spinning forever here would hold the
                # thread lock and wedge every access to the file.
                if time.time() - start_time > timeout:
                    raise TimeoutError(
                        f"Could not acquire lock for {target.name} within {timeout} seconds."
                    ) from exc
                time.sleep(0.05)

        yield
    finally:
        if acquired_file:
            with suppress(OSError):
                lock_path.unlink()
