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


if __name__ == "__main__":
    unittest.main()
