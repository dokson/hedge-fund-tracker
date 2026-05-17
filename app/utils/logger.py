import logging
import sys
from typing import cast

_CONFIGURED = False

# Custom levels.
#   PROGRESS / MONEY / SUCCESS sit just above INFO so they're emitted by
#   default and render with their respective marker via _PrefixFormatter.
#   DEPRECATED sits between WARNING and ERROR.
PROGRESS = 22
MONEY = 23
SUCCESS = 25
DEPRECATED = 35
logging.addLevelName(PROGRESS, "PROGRESS")
logging.addLevelName(MONEY, "MONEY")
logging.addLevelName(SUCCESS, "SUCCESS")
logging.addLevelName(DEPRECATED, "DEPRECATED")


def log_safe(value: object, max_len: int = 64) -> str:
    """
    Sanitize an identifier before interpolating it into a log line.

    Strips non-printable characters (newlines, ANSI escapes, NUL bytes) and
    truncates so a malicious or malformed value can't forge log entries or
    break the per-line format used by the SSE pipeline in ``app.server``.

    Apply anywhere a user-controlled or externally-sourced string (CUSIP,
    ticker, fund name, CSV row field, scraped XML attribute) flows into a
    ``logger.X(...)`` call. Prefer lazy ``%``-formatting over f-strings so
    the sanitized value is the one ultimately serialized:

        logger.warning("No company for CUSIP %s", log_safe(cusip))
    """
    cleaned = "".join(c for c in str(value) if c.isprintable())
    if len(cleaned) > max_len:
        cleaned = cleaned[: max_len - 1] + "…"
    return cleaned


def _attach_emoji(kwargs: dict, emoji: str | None) -> None:
    """
    Stash an explicit ``emoji=`` override onto the LogRecord via ``extra``.
    Picked up by ``_PrefixFormatter`` to replace the default level marker.
    """
    if emoji is not None:
        kwargs.setdefault("extra", {})["emoji"] = emoji


def _bump_stacklevel(kwargs: dict, n: int) -> None:
    """
    Bump ``stacklevel`` by ``n`` so logging's findCaller() skips our wrapper
    frames and records the actual call site for ``%(filename)s``/``%(lineno)d``.
    """
    kwargs["stacklevel"] = kwargs.get("stacklevel", 1) + n


class _StyledLogger(logging.Logger):
    """
    Project-specific Logger subclass.

    Adds an ``emoji=`` keyword to the five standard level methods, plus four
    custom levels (``success``/``progress``/``money``/``deprecated``).

    Scoped via ``logging.setLoggerClass`` instead of monkey-patching
    ``logging.Logger`` directly, so third-party loggers (uvicorn,
    sqlalchemy, fastapi_users, ...) keep stock behaviour and our custom
    method names cannot collide with future stdlib additions.
    """

    def debug(self, msg, *args, emoji: str | None = None, **kwargs):
        _attach_emoji(kwargs, emoji)
        _bump_stacklevel(kwargs, 1)
        super().debug(msg, *args, **kwargs)

    def info(self, msg, *args, emoji: str | None = None, **kwargs):
        _attach_emoji(kwargs, emoji)
        _bump_stacklevel(kwargs, 1)
        super().info(msg, *args, **kwargs)

    def warning(self, msg, *args, emoji: str | None = None, **kwargs):
        _attach_emoji(kwargs, emoji)
        _bump_stacklevel(kwargs, 1)
        super().warning(msg, *args, **kwargs)

    def error(self, msg, *args, emoji: str | None = None, **kwargs):
        _attach_emoji(kwargs, emoji)
        _bump_stacklevel(kwargs, 1)
        super().error(msg, *args, **kwargs)

    def critical(self, msg, *args, emoji: str | None = None, **kwargs):
        _attach_emoji(kwargs, emoji)
        _bump_stacklevel(kwargs, 1)
        super().critical(msg, *args, **kwargs)

    def _custom(self, level: int, msg, args, kwargs, emoji: str | None) -> None:
        _attach_emoji(kwargs, emoji)
        # Skip both _custom and the public wrapper (success/progress/money/
        # deprecated) so findCaller lands on the actual call site.
        _bump_stacklevel(kwargs, 2)
        if self.isEnabledFor(level):
            self._log(level, msg, args, **kwargs)

    def success(self, msg, *args, emoji: str | None = None, **kwargs) -> None:
        self._custom(SUCCESS, msg, args, kwargs, emoji)

    def progress(self, msg, *args, emoji: str | None = None, **kwargs) -> None:
        self._custom(PROGRESS, msg, args, kwargs, emoji)

    def money(self, msg, *args, emoji: str | None = None, **kwargs) -> None:
        self._custom(MONEY, msg, args, kwargs, emoji)

    def deprecated(self, msg, *args, emoji: str | None = None, **kwargs) -> None:
        self._custom(DEPRECATED, msg, args, kwargs, emoji)


logging.setLoggerClass(_StyledLogger)


class _PrefixFormatter(logging.Formatter):
    """
    Prepend a per-level (or per-call) emoji prefix to every record.

    Resolution order:
      1. ``record.emoji`` if set via ``logger.X("msg", emoji="🔥")`` — overrides default.
      2. The default level-based prefix (WARNING/ERROR/CRITICAL/DEPRECATED).
      3. No prefix for INFO/DEBUG without an emoji= kwarg.
    """

    # Note: ``⚠️`` (U+26A0 + U+FE0F variation selector) is rendered as a
    # double-width emoji on most terminals and visually swallows a single
    # trailing space. Use a double space after it to keep the marker
    # separated from the message.
    _PREFIXES = {
        logging.DEBUG: "🚧 ",
        logging.INFO: "ℹ️  ",
        PROGRESS: "⏳ ",
        MONEY: "💲 ",
        SUCCESS: "✅ ",
        DEPRECATED: "⚠️  DEPRECATED: ",
        logging.WARNING: "🚨 WARNING: ",
        logging.ERROR: "❌ ERROR - ",
        logging.CRITICAL: "❌ CRITICAL - ",
    }

    def format(self, record: logging.LogRecord) -> str:
        custom = getattr(record, "emoji", None)
        prefix = f"{custom} " if custom else self._PREFIXES.get(record.levelno, "")
        return prefix + super().format(record)


def _configure_root_once() -> None:
    """
    Attach a single StreamHandler(sys.stdout) to the root logger.

    sys.stdout is intentionally read at handler-emit time (not at handler
    construction) so the handler stays compatible with app.server's
    _ContextAwareStdout wrapper, which replaces sys.stdout after import.
    """
    global _CONFIGURED
    if _CONFIGURED:
        return

    class _StdoutHandler(logging.StreamHandler):
        """
        StreamHandler that resolves sys.stdout lazily on every emit.

        Necessary because app.server swaps sys.stdout with a context-aware
        wrapper after import; a handler bound to the original stream would
        bypass the per-request SSE queue.
        """

        @property
        def stream(self):
            return sys.stdout

        @stream.setter
        def stream(self, value):
            # Ignore writes — we always defer to current sys.stdout.
            pass

    handler = _StdoutHandler()
    handler.setFormatter(_PrefixFormatter("%(message)s"))

    root = logging.getLogger()
    root.handlers = [h for h in root.handlers if not isinstance(h, _StdoutHandler)]
    root.addHandler(handler)
    root.setLevel(logging.INFO)
    _CONFIGURED = True


def get_logger(name: str) -> _StyledLogger:
    """
    Return a module-scoped logger that streams to current sys.stdout.

    Drop-in replacement for ``print()`` in status/error reporting paths
    while preserving compatibility with the SSE log-capture pipeline in
    app.server. Records at WARNING/ERROR/CRITICAL/DEPRECATED/SUCCESS/
    PROGRESS/MONEY level are auto-prefixed with the matching emoji marker —
    call sites should not repeat the marker in the message body.

    The returned logger is a ``_StyledLogger`` (registered via
    ``logging.setLoggerClass``) with ``.success/.progress/.money/.deprecated``
    available and an optional ``emoji=`` keyword on every level.
    """
    _configure_root_once()
    return cast(_StyledLogger, logging.getLogger(name))
