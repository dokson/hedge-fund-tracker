from app.utils.encoding import use_utf8_stdio

use_utf8_stdio()

# Safety net: ensure the shared logger handler + custom levels are installed
# even if a future entry point doesn't import any module that uses get_logger().
# Idempotent (the configure is guarded by a module-level _CONFIGURED flag).
from app.utils import logger as _logger  # noqa: E402, F401
