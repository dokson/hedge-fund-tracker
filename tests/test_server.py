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

    def test_database_get_route_exists(self):
        """
        Verify that the GET endpoint for serving database files is registered.
        """
        from app.server import app
        routes = [r.path for r in app.routes]
        self.assertIn("/database/{filepath:path}", routes)

    def test_database_put_route_exists(self):
        """
        Verify that the PUT endpoint for updating database files is registered.
        """
        from app.server import app
        routes = [r.path for r in app.routes]
        # PUT uses same path as GET
        self.assertIn("/database/{filepath:path}", routes)

    def test_env_get_route_exists(self):
        """
        Verify that the endpoint for reading environment variables is registered.
        """
        from app.server import app
        routes = [r.path for r in app.routes]
        self.assertIn("/api/settings/env", routes)

    def test_ai_promise_score_route_exists(self):
        """
        Verify that the AI Promise Score analysis endpoint is registered.
        """
        from app.server import app
        routes = [r.path for r in app.routes]
        self.assertIn("/api/ai/promise-score", routes)

    def test_ai_due_diligence_route_exists(self):
        """
        Verify that the AI Due Diligence analysis endpoint is registered.
        """
        from app.server import app
        routes = [r.path for r in app.routes]
        self.assertIn("/api/ai/due-diligence", routes)

    def test_database_fetch_route_exists(self):
        """
        Verify that the database fetch endpoint is registered.
        """
        from app.server import app
        routes = [r.path for r in app.routes]
        self.assertIn("/api/database/fetch", routes)

    def test_latest_quarter_route_exists(self):
        """
        Verify that the dedicated latest-quarter endpoint is registered, and that
        it is registered BEFORE the parameterized /{quarter} route so FastAPI
        matches the literal "latest" path first.
        """
        from app.server import app
        paths = [r.path for r in app.routes]
        self.assertIn("/api/database/quarters/latest", paths)
        latest_idx = paths.index("/api/database/quarters/latest")
        param_idx = paths.index("/api/database/quarters/{quarter}")
        self.assertLess(latest_idx, param_idx)

    def test_quarter_analysis_route_exists(self):
        """
        Verify that the per-quarter aggregated analysis endpoint is registered.
        """
        from app.server import app
        routes = [r.path for r in app.routes]
        self.assertIn("/api/database/quarters/{quarter}/analysis", routes)


if __name__ == "__main__":
    unittest.main()
