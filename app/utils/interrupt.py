from __future__ import annotations

import sys
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sys import UnraisableHookArgs


def install_keyboardinterrupt_filter() -> Callable[..., Any]:
    """
    Installs a sys.unraisablehook that silently drops KeyboardInterrupt and
    SystemExit raised inside C callbacks, and returns the active hook.

    When Ctrl+C lands while a C callback is on the stack (e.g. curl_cffi's
    buffer_callback during an in-flight HTTP request, reached transitively via
    yfinance), the resulting KeyboardInterrupt cannot propagate out of the C
    layer, so CPython routes it to sys.unraisablehook. The default hook prints
    a noisy "Exception ignored from cffi callback" trace — surfaced as a popup
    dialog on Windows. The genuine KeyboardInterrupt is still delivered to the
    main thread and handled by the CLI's own try/except, so dropping this
    unraisable copy is safe. Non-interrupt unraisables (real bugs in __del__
    methods, weakref callbacks, etc.) are forwarded to the previous hook
    unchanged so they stay visible.

    Idempotent: a marker attribute on the installed wrapper prevents
    double-wrapping if called more than once.
    """
    previous = sys.unraisablehook
    if getattr(previous, "_kbi_filter", False):
        return previous

    def hook(unraisable: UnraisableHookArgs) -> None:
        """
        Drops unraisable KeyboardInterrupt/SystemExit; forwards the rest.
        """
        exc_type = unraisable.exc_type
        if exc_type is not None and issubclass(exc_type, (KeyboardInterrupt, SystemExit)):
            return
        previous(unraisable)

    hook._kbi_filter = True  # type: ignore[attr-defined]
    sys.unraisablehook = hook
    return hook
