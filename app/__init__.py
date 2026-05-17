import sys

for _stream in (sys.stdout, sys.stderr):
    _reconfigure = getattr(_stream, "reconfigure", None)
    if _reconfigure is not None:
        _reconfigure(encoding="utf-8")

# Safety net: ensure the shared logger handler + custom levels are installed
# even if a future entry point doesn't import any module that uses get_logger().
# Idempotent (the configure is guarded by a module-level _CONFIGURED flag).
from app.utils import logger as _logger  # noqa: E402, F401
