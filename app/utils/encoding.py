"""
UTF-8 for the standard streams, set once for every entry point: `import app`
calls it, so CLIs, scripts and the server never need `python -X utf8`.
"""

import sys


def use_utf8_stdio() -> None:
    """
    Switch stdout/stderr to UTF-8 so emoji log markers don't crash cp1252 consoles.
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8")
