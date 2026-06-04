import unittest

import numpy as np
import pandas as pd

try:
    import app.server  # noqa: F401 — probe import; tests do their own imports lazily.
except ImportError as _e:  # pragma: no cover — optional dep missing (e.g. fastapi_users)
    raise unittest.SkipTest(f"app.server unavailable: {_e}") from None


class TestDfToJsonSafeRecords(unittest.TestCase):
    """
    Tests for the _df_to_json_safe_records helper that sanitizes ±Infinity and NaN
    so the records can be JSON-encoded without producing the non-standard tokens
    'Infinity' / 'NaN' that browsers reject.
    """

    def test_replaces_infinity_with_none(self):
        """
        Positive and negative infinity values must be converted to None.
        """
        from app.api.common import _df_to_json_safe_records

        df = pd.DataFrame({"a": [1.0, np.inf, -np.inf]})
        records = _df_to_json_safe_records(df)
        self.assertEqual(records, [{"a": 1.0}, {"a": None}, {"a": None}])

    def test_replaces_nan_with_none(self):
        """
        NaN must be converted to None even on float64 columns (regression test for
        the dtype bug where .where(..., None) was silently a no-op on numeric dtypes).
        """
        from app.api.common import _df_to_json_safe_records

        df = pd.DataFrame({"a": [1.0, np.nan]})
        records = _df_to_json_safe_records(df)
        self.assertEqual(records, [{"a": 1.0}, {"a": None}])

    def test_preserves_string_columns(self):
        """
        Non-numeric columns must pass through untouched.
        """
        from app.api.common import _df_to_json_safe_records

        df = pd.DataFrame({"a": [1.0, np.inf], "b": ["x", "y"]})
        records = _df_to_json_safe_records(df)
        self.assertEqual(records, [{"a": 1.0, "b": "x"}, {"a": None, "b": "y"}])

    def test_output_is_strict_json_serializable(self):
        """
        The result must be JSON-encodable with allow_nan=False (i.e. browser-safe).
        """
        import json

        from app.api.common import _df_to_json_safe_records

        df = pd.DataFrame({"a": [np.inf, np.nan, 0.5]})
        records = _df_to_json_safe_records(df)
        json.dumps(records, allow_nan=False)

    def test_empty_dataframe_returns_empty_list(self):
        """
        An empty DataFrame must produce an empty record list, not raise.
        """
        from app.api.common import _df_to_json_safe_records

        records = _df_to_json_safe_records(pd.DataFrame())
        self.assertEqual(records, [])


class TestServer(unittest.TestCase):
    """
    Tests for the FastAPI server module and its route configuration.
    """

    def test_expected_routes_are_registered(self):
        """
        Verify that all expected API and database routes are registered on the FastAPI app.
        """
        from app.server import app

        paths = [getattr(r, "path", "") for r in app.routes]

        expected_paths = [
            "/database/{filepath:path}",
            "/api/settings/env",
            "/api/ai/promise-score",
            "/api/ai/due-diligence",
            "/api/database/fetch",
            "/api/database/quarters/latest",
            "/api/database/quarters/{quarter}/analysis",
        ]
        for path in expected_paths:
            with self.subTest(path=path):
                self.assertIn(path, paths)

    def test_latest_quarter_route_is_registered_before_parameterized_quarter(self):
        """
        FastAPI matches routes in registration order, so the literal "/latest"
        endpoint must precede "/{quarter}" to avoid being shadowed.
        """
        from app.server import app

        paths = [getattr(r, "path", "") for r in app.routes]
        latest_idx = paths.index("/api/database/quarters/latest")
        param_idx = paths.index("/api/database/quarters/{quarter}")
        self.assertLess(latest_idx, param_idx)


class TestSSEContextIsolation(unittest.TestCase):
    """
    Tests that the SSE stdout-capture mechanism (`_ContextAwareStdout` +
    `_request_log_q`) isolates concurrent requests. Each request must only see
    its own prints, never another request's output. This is the contract that
    makes the server multi-tenant safe.
    """

    def test_two_concurrent_runners_do_not_mix_output(self):
        """
        Run two SSE-style targets concurrently from different threads. Each
        prints its own marker; the queues bound to each context must contain
        only that context's marker, never the other's.
        """
        import threading

        from app.server import _request_log_q

        q_a: queue.SimpleQueue[tuple[str, str]] = queue.SimpleQueue()
        q_b: queue.SimpleQueue[tuple[str, str]] = queue.SimpleQueue()
        barrier = threading.Barrier(2)

        def runner(q, marker):
            token = _request_log_q.set(q)
            try:
                barrier.wait()  # ensure both threads are inside the context simultaneously
                for _ in range(20):
                    print(marker)
            finally:
                _request_log_q.reset(token)

        ta = threading.Thread(target=runner, args=(q_a, "AAA"))
        tb = threading.Thread(target=runner, args=(q_b, "BBB"))
        ta.start()
        tb.start()
        ta.join()
        tb.join()

        a_lines = []
        while not q_a.empty():
            a_lines.append(q_a.get_nowait()[1])
        b_lines = []
        while not q_b.empty():
            b_lines.append(q_b.get_nowait()[1])

        self.assertEqual(a_lines, ["AAA"] * 20)
        self.assertEqual(b_lines, ["BBB"] * 20)

    def test_print_outside_context_falls_through_to_real_stdout(self):
        """
        When no contextvar is set (e.g. uvicorn logs, CLI mode), `print()` must
        pass through to the original stdout instead of being swallowed.
        """
        import io

        from app.server import _ContextAwareStdout, _request_log_q

        buf = io.StringIO()
        wrapper = _ContextAwareStdout(buf)

        # Sanity: contextvar is None outside any handler.
        self.assertIsNone(_request_log_q.get())

        wrapper.write("hello\n")
        self.assertEqual(buf.getvalue(), "hello\n")


class TestSSETerminalSignal(unittest.TestCase):
    """
    Tests that the SSE worker always enqueues a terminal ("result"/"error") item,
    on every exit path. If it didn't, the consumer's blocking `log_q.get()` would
    hang forever — leaking an executor thread and an open HTTP connection.
    """

    def test_normal_result_emits_result_item(self):
        """
        A target that returns a value enqueues a single ("result", value) item.
        """
        from app.server import _run_sse_target

        q: queue.SimpleQueue = queue.SimpleQueue()
        _run_sse_target(lambda: {"ok": 1}, q)

        self.assertEqual(q.get_nowait(), ("result", {"ok": 1}))
        self.assertTrue(q.empty())

    def test_exception_emits_error_item(self):
        """
        A target that raises a regular Exception enqueues an ("error", msg) item.
        """
        from app.server import _run_sse_target

        q: queue.SimpleQueue = queue.SimpleQueue()

        def target():
            raise ValueError("boom")

        _run_sse_target(target, q)
        kind, payload = q.get_nowait()
        self.assertEqual(kind, "error")
        self.assertIn("boom", payload)

    def test_base_exception_still_emits_terminal_item(self):
        """
        Even a BaseException (SystemExit, KeyboardInterrupt) must produce a
        terminal item so the consumer never blocks forever. This is the gap the
        old `except Exception` left open.
        """
        from app.server import _run_sse_target

        q: queue.SimpleQueue = queue.SimpleQueue()

        def target():
            raise SystemExit("shutdown mid-stream")

        _run_sse_target(target, q)
        self.assertEqual(q.get_nowait()[0], "error")
        self.assertTrue(q.empty())

    def test_contextvar_is_reset_after_run(self):
        """
        The per-request contextvar must be reset on exit so the worker thread
        (and any thread reusing the context) doesn't leak the queue binding.
        """
        from app.server import _request_log_q, _run_sse_target

        q: queue.SimpleQueue = queue.SimpleQueue()
        _run_sse_target(lambda: None, q)
        self.assertIsNone(_request_log_q.get())


class TestLifespanDisposesEngine(unittest.IsolatedAsyncioTestCase):
    """
    The module-level async engine owns a connection pool. The lifespan shutdown
    must dispose it so pooled connections close gracefully instead of relying on
    process exit.
    """

    async def test_engine_disposed_on_shutdown(self):
        """
        Exiting the lifespan context must await engine.dispose() exactly once.
        """
        from unittest.mock import AsyncMock, MagicMock, patch

        import app.server as server

        fake_engine = MagicMock()
        fake_engine.dispose = AsyncMock()
        with (
            patch("app.security.envelope._kek"),
            patch("app.db.session.engine", fake_engine),
        ):
            async with server._lifespan(server.app):
                pass

        fake_engine.dispose.assert_awaited_once()


# Make `queue` available to the SSE isolation test without polluting module top
import queue  # noqa: E402

if __name__ == "__main__":
    unittest.main()
