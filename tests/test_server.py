import unittest

import numpy as np
import pandas as pd


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
        from app.server import _df_to_json_safe_records

        df = pd.DataFrame({"a": [1.0, np.inf, -np.inf]})
        records = _df_to_json_safe_records(df)
        self.assertEqual(records, [{"a": 1.0}, {"a": None}, {"a": None}])

    def test_replaces_nan_with_none(self):
        """
        NaN must be converted to None even on float64 columns (regression test for
        the dtype bug where .where(..., None) was silently a no-op on numeric dtypes).
        """
        from app.server import _df_to_json_safe_records

        df = pd.DataFrame({"a": [1.0, np.nan]})
        records = _df_to_json_safe_records(df)
        self.assertEqual(records, [{"a": 1.0}, {"a": None}])

    def test_preserves_string_columns(self):
        """
        Non-numeric columns must pass through untouched.
        """
        from app.server import _df_to_json_safe_records

        df = pd.DataFrame({"a": [1.0, np.inf], "b": ["x", "y"]})
        records = _df_to_json_safe_records(df)
        self.assertEqual(records, [{"a": 1.0, "b": "x"}, {"a": None, "b": "y"}])

    def test_output_is_strict_json_serializable(self):
        """
        The result must be JSON-encodable with allow_nan=False (i.e. browser-safe).
        """
        import json

        from app.server import _df_to_json_safe_records

        df = pd.DataFrame({"a": [np.inf, np.nan, 0.5]})
        records = _df_to_json_safe_records(df)
        json.dumps(records, allow_nan=False)

    def test_empty_dataframe_returns_empty_list(self):
        """
        An empty DataFrame must produce an empty record list, not raise.
        """
        from app.server import _df_to_json_safe_records

        records = _df_to_json_safe_records(pd.DataFrame())
        self.assertEqual(records, [])


class TestServer(unittest.TestCase):
    """
    Tests for the FastAPI server module and its route configuration.
    """

    def test_server_module_is_importable(self):
        """
        Verify that the server module can be imported without errors.
        """
        from app.server import app

        self.assertIsNotNone(app)

    def test_app_is_fastapi_instance(self):
        """
        Verify that the exported app object is a FastAPI instance.
        """
        from fastapi import FastAPI

        from app.server import app

        self.assertIsInstance(app, FastAPI)

    def test_expected_routes_are_registered(self):
        """
        Verify that all expected API and database routes are registered on the FastAPI app.
        """
        from app.server import app

        paths = [r.path for r in app.routes]

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

        paths = [r.path for r in app.routes]
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


# Make `queue` available to the SSE isolation test without polluting module top
import queue  # noqa: E402

if __name__ == "__main__":
    unittest.main()
