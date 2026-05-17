import io
import logging
import sys
import threading
import unittest

from app.utils.logger import get_logger


class TestGetLogger(unittest.TestCase):
    """
    Verifies the logger streams to sys.stdout *as resolved at emit time*,
    so app.server's _ContextAwareStdout (which replaces sys.stdout after
    import) still captures every log record for SSE delivery.
    """

    def setUp(self):
        """
        Replace sys.stdout with a capture buffer for each test.
        """
        self._orig_stdout = sys.stdout
        self.addCleanup(setattr, sys, "stdout", self._orig_stdout)

    def test_info_message_reaches_current_stdout(self):
        """
        logger.info() must write to whatever sys.stdout points to at emit time.
        """
        buf = io.StringIO()
        sys.stdout = buf

        logger = get_logger("test.info")
        logger.info("hello")

        self.assertIn("hello", buf.getvalue())

    def test_error_message_reaches_current_stdout(self):
        """
        logger.error() goes to the same stream — there is no separate stderr
        path that would bypass SSE capture.
        """
        buf = io.StringIO()
        sys.stdout = buf

        logger = get_logger("test.error")
        logger.error("kaboom")

        self.assertIn("kaboom", buf.getvalue())

    def test_stdout_swap_after_logger_creation_is_honored(self):
        """
        Replacing sys.stdout *after* get_logger() must still route writes
        to the new stream — proving the handler resolves the stream lazily.
        """
        logger = get_logger("test.lazy")

        new_buf = io.StringIO()
        sys.stdout = new_buf
        logger.info("post-swap")

        self.assertIn("post-swap", new_buf.getvalue())

    def test_exc_info_emits_traceback(self):
        """
        logger.error(..., exc_info=True) preserves the original traceback —
        the diagnostic gap that the print-and-swallow pattern was hiding.
        """
        buf = io.StringIO()
        sys.stdout = buf

        logger = get_logger("test.exc")
        try:
            raise ValueError("root cause")
        except ValueError:
            logger.error("wrapper", exc_info=True)

        out = buf.getvalue()
        self.assertIn("wrapper", out)
        self.assertIn("ValueError", out)
        self.assertIn("root cause", out)

    def test_sse_style_stdout_wrapper_receives_log_records(self):
        """
        Simulates app.server's _ContextAwareStdout pattern: a wrapper around
        sys.stdout that captures writes for per-request SSE delivery. Logger
        records must reach the wrapper's write() so the AI Due Diligence
        terminal-like UI keeps streaming after the print→logger migration.
        """
        captured: list[str] = []

        class _SSEStdoutWrapper:
            """
            Stand-in for _ContextAwareStdout — records every write call.
            """

            def write(self, text):
                captured.append(text)
                return len(text)

            def flush(self):
                pass

        # Mimic the post-import swap in app.server.
        sys.stdout = _SSEStdoutWrapper()

        logger = get_logger("test.sse")
        logger.info("ranking ticker AAPL")
        logger.error("upstream API failed")

        joined = "".join(captured)
        self.assertIn("ranking ticker AAPL", joined)
        self.assertIn("upstream API failed", joined)

    def test_warning_records_get_warning_prefix(self):
        """
        logger.warning() output must start with the configured 🚨 WARNING: prefix.
        """
        buf = io.StringIO()
        sys.stdout = buf

        get_logger("test.prefix.warn").warning("low disk")

        self.assertIn("🚨 WARNING: low disk", buf.getvalue())

    def test_error_records_get_error_prefix(self):
        """
        logger.error() output must start with the configured ❌ ERROR - prefix.
        """
        buf = io.StringIO()
        sys.stdout = buf

        get_logger("test.prefix.err").error("upstream down")

        self.assertIn("❌ ERROR - upstream down", buf.getvalue())

    def test_progress_method_emits_with_hourglass_prefix(self):
        """
        logger.progress() renders with the ⏳ marker — used for "trying" /
        "fallback" / "in flight" status messages.
        """
        buf = io.StringIO()
        sys.stdout = buf

        get_logger("test.progress").progress("fetching ticker AAPL")

        self.assertIn("⏳ fetching ticker AAPL", buf.getvalue())

    def test_money_method_emits_with_dollar_prefix(self):
        """
        logger.money() renders with the 💲 marker — used for price/value reporting.
        """
        buf = io.StringIO()
        sys.stdout = buf

        get_logger("test.money").money("price for AAPL: $150.00")

        self.assertIn("💲 price for AAPL: $150.00", buf.getvalue())

    def test_success_method_emits_with_success_prefix(self):
        """
        logger.success() emits at the SUCCESS level with the ✅ marker via the
        formatter — call sites avoid baking the emoji into every message.
        """
        buf = io.StringIO()
        sys.stdout = buf

        get_logger("test.success").success("scrape complete")

        self.assertIn("✅ scrape complete", buf.getvalue())

    def test_deprecated_method_emits_with_deprecation_prefix(self):
        """
        logger.deprecated() must be available on every logger and prepend
        the ⚠️ DEPRECATED: marker via the formatter.
        """
        buf = io.StringIO()
        sys.stdout = buf

        get_logger("test.prefix.dep").deprecated("old API removed in v2")

        # Double space after ⚠️ — see note in _PrefixFormatter._PREFIXES.
        self.assertIn("⚠️  DEPRECATED: old API removed in v2", buf.getvalue())

    def test_info_with_emoji_kwarg_gets_custom_prefix(self):
        """
        Stylistic emoji passed via emoji= becomes the message prefix on info.
        """
        buf = io.StringIO()
        sys.stdout = buf

        get_logger("test.styled.info").info("scrape complete", emoji="✅")

        self.assertIn("✅ scrape complete", buf.getvalue())

    def test_emoji_kwarg_overrides_level_default_prefix(self):
        """
        An explicit emoji= overrides the level's default marker — e.g. a
        warning with emoji="🔥" emits 🔥 instead of 🚨 WARNING:.
        """
        buf = io.StringIO()
        sys.stdout = buf

        get_logger("test.styled.warn").warning("hot path", emoji="🔥")

        out = buf.getvalue()
        self.assertIn("🔥 hot path", out)
        self.assertNotIn("🚨 WARNING:", out)

    def test_info_records_default_to_info_marker(self):
        """
        Plain info logs gain the default ℹ️ marker; ERROR/WARNING markers
        must not bleed into info output.
        """
        buf = io.StringIO()
        sys.stdout = buf

        get_logger("test.prefix.info").info("ranking complete")

        out = buf.getvalue()
        self.assertIn("ℹ️  ranking complete", out)
        self.assertNotIn("❌", out)
        self.assertNotIn("🚨", out)
        self.assertNotIn("⚠️ ", out)

    def test_info_with_emoji_kwarg_overrides_info_marker(self):
        """
        emoji= on info still wins over the default ℹ️ prefix.
        """
        buf = io.StringIO()
        sys.stdout = buf

        get_logger("test.info.override").info("rebuilding", emoji="🔄")

        out = buf.getvalue()
        self.assertIn("🔄 rebuilding", out)
        self.assertNotIn("ℹ️", out)

    def test_caller_filename_is_not_the_logger_module(self):
        """
        ``LogRecord.filename`` / ``lineno`` must point to the call site, not
        to our ``_StyledLogger.info`` override frame. Forward-looking: if a
        future format string adds ``%(filename)s`` or ``%(lineno)d``, every
        line would otherwise report ``app/utils/logger.py`` instead of the
        actual caller.

        Covers all 9 levels (standard + custom).
        """
        captured: list[logging.LogRecord] = []

        class _CaptureHandler(logging.Handler):
            def emit(self, record):
                captured.append(record)

        handler = _CaptureHandler()
        logger = get_logger("test.caller")
        logger.addHandler(handler)
        self.addCleanup(logger.removeHandler, handler)
        # Lower per-logger threshold so debug records propagate to the handler.
        logger.setLevel(logging.DEBUG)

        logger.debug("via debug")
        logger.info("via info")
        logger.warning("via warning")
        logger.error("via error")
        logger.critical("via critical")
        logger.success("via success")
        logger.progress("via progress")
        logger.money("via money")
        logger.deprecated("via deprecated")

        self.assertEqual(len(captured), 9)
        for record in captured:
            with self.subTest(level=record.levelname):
                self.assertTrue(
                    record.filename.endswith("test_logger.py"),
                    f"{record.levelname} recorded filename={record.filename!r}, "
                    f"expected test_logger.py (call site, not logger.py override)",
                )

    def test_concurrent_writes_do_not_interleave_within_a_record(self):
        """
        Records emitted from many threads must reach stdout intact — the
        prefix, body, and trailing newline of a single ``logger.X`` call
        cannot be split by another thread's write.

        Regression guard for the worker-thread stdout interleaving concern
        raised during the parallelization audit. Python's stdlib logging
        serializes ``Handler.emit()`` via an RLock; this test pins that
        guarantee so a future custom handler that drops the lock fails fast.
        """
        buf = io.StringIO()
        sys.stdout = buf

        n_threads = 8
        per_thread = 25
        barrier = threading.Barrier(n_threads)
        logger = get_logger("test.concurrency")

        def worker(idx):
            barrier.wait()
            for i in range(per_thread):
                logger.info("thread%s_msg%s", idx, i)

        threads = [threading.Thread(target=worker, args=(t,)) for t in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        lines = [line for line in buf.getvalue().splitlines() if line]
        self.assertEqual(len(lines), n_threads * per_thread)

        # Every line must end with the expected marker (no truncation), and
        # every (thread, i) pair must appear exactly once.
        seen: set[tuple[int, int]] = set()
        for line in lines:
            # Lines look like "ℹ️  thread3_msg17"; the marker must be at start.
            self.assertTrue(line.startswith("ℹ️"), f"missing info prefix: {line!r}")
            payload = line.split(" ", 2)[-1]
            t_part, i_part = payload.split("_")
            seen.add((int(t_part.removeprefix("thread")), int(i_part.removeprefix("msg"))))

        expected = {(t, i) for t in range(n_threads) for i in range(per_thread)}
        self.assertEqual(seen, expected)

    def test_level_filters_debug_by_default(self):
        """
        Default level is INFO; DEBUG records are filtered out.
        """
        buf = io.StringIO()
        sys.stdout = buf

        logger = get_logger("test.debug")
        # Force level back to INFO in case a prior test mutated it.
        logging.getLogger().setLevel(logging.INFO)
        logger.debug("invisible")

        self.assertNotIn("invisible", buf.getvalue())

    def test_debug_records_get_construction_prefix_when_enabled(self):
        """
        When root level is lowered to DEBUG, logger.debug() emits with the 🚧 marker.
        """
        buf = io.StringIO()
        sys.stdout = buf

        logger = get_logger("test.debug.prefix")
        self.addCleanup(logging.getLogger().setLevel, logging.INFO)
        logging.getLogger().setLevel(logging.DEBUG)

        logger.debug("inspecting state")

        self.assertIn("🚧 inspecting state", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
