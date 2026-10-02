import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from prometheus_client import REGISTRY

from app.api.observability import RequestContextMiddleware
from app.utils.logger import get_logger, request_id_var


def _requests_total(method: str, route: str, status: str) -> float:
    """
    Current value of the HTTP request counter for one label set.
    """
    labels = {"method": method, "route": route, "status": status}
    return REGISTRY.get_sample_value("hft_http_requests_total", labels) or 0.0


def _build_app() -> FastAPI:
    """
    Minimal app wrapped by the middleware, with templated and failing routes.
    """
    app = FastAPI()

    @app.get("/api/items/{item_id}")
    def item(item_id: str) -> dict[str, str | None]:
        """
        Echo the request id visible to the handler.
        """
        get_logger("test.observability.handler").info("handling %s", item_id)
        return {"request_id": request_id_var.get()}

    @app.get("/health")
    def health() -> dict[str, str]:
        """
        Probe endpoint excluded from the access log.
        """
        return {"status": "ok"}

    @app.get("/api/boom")
    def boom() -> None:
        """
        Fail with an unhandled exception.
        """
        raise RuntimeError("boom")

    app.add_middleware(RequestContextMiddleware)
    return app


class TestRequestContextMiddleware(unittest.TestCase):
    def setUp(self):
        """
        Fresh client per test; unhandled errors become 500 responses.
        """
        self.client = TestClient(_build_app(), raise_server_exceptions=False)

    def test_generates_a_request_id_when_none_is_sent(self):
        """
        Every response carries an id, the same one the handler saw.
        """
        response = self.client.get("/api/items/1")

        request_id = response.headers["X-Request-ID"]
        self.assertRegex(request_id, r"^[0-9a-f]{32}$")
        self.assertEqual(response.json()["request_id"], request_id)

    def test_propagates_a_sane_incoming_request_id(self):
        """
        An upstream id that is short and safe is reused end to end.
        """
        response = self.client.get("/api/items/1", headers={"X-Request-ID": "edge-42.a_b"})

        self.assertEqual(response.headers["X-Request-ID"], "edge-42.a_b")
        self.assertEqual(response.json()["request_id"], "edge-42.a_b")

    def test_replaces_an_unsafe_incoming_request_id(self):
        """
        An id that could forge log lines or blow up cardinality is replaced.
        """
        for bad in ("x" * 129, "evil id", "a\tb", ""):
            with self.subTest(bad=bad):
                response = self.client.get("/api/items/1", headers={"X-Request-ID": bad})

                self.assertRegex(response.headers["X-Request-ID"], r"^[0-9a-f]{32}$")

    def test_request_id_is_unbound_after_the_request(self):
        """
        The id does not leak into code running after the request.
        """
        self.client.get("/api/items/1")

        self.assertIsNone(request_id_var.get())

    def test_logs_one_access_line_per_request(self):
        """
        The access line has method, path, status and duration in ms.
        """
        with self.assertLogs("app.api.observability", level="INFO") as logs:
            self.client.get("/api/items/7")

        self.assertEqual(len(logs.records), 1)
        self.assertRegex(logs.output[0], r"GET /api/items/7 200 \d+(\.\d+)? ms")

    def test_access_line_carries_the_request_id(self):
        """
        The access record is emitted while the request id is still bound.
        """
        import logging

        from app.utils.logger import _RequestIdFilter

        records: list[logging.LogRecord] = []
        handler = logging.Handler()
        handler.emit = records.append  # type: ignore[method-assign]
        handler.addFilter(_RequestIdFilter())
        access_logger = logging.getLogger("app.api.observability")
        access_logger.addHandler(handler)
        self.addCleanup(access_logger.removeHandler, handler)

        response = self.client.get("/api/items/7")

        self.assertEqual(len(records), 1)
        self.assertEqual(getattr(records[0], "request_id", None), response.headers["X-Request-ID"])

    def test_health_and_static_assets_are_not_logged(self):
        """
        Probes and asset fetches would drown the access log.
        """
        app = _build_app()

        @app.get("/{full_path:path}")
        def spa(full_path: str) -> dict[str, str]:
            """
            Catch-all standing in for the static/SPA route.
            """
            return {"path": full_path}

        client = TestClient(app)
        with self.assertNoLogs("app.api.observability", level="INFO"):
            client.get("/health")
            client.get("/assets/index-abc123.js")
            client.get("/database/stocks.csv")

    def test_counts_requests_by_route_template(self):
        """
        The route label is the template, so ids in the path don't create series.
        """
        before = _requests_total("GET", "/api/items/{item_id}", "200")

        self.client.get("/api/items/1")
        self.client.get("/api/items/2")

        self.assertEqual(_requests_total("GET", "/api/items/{item_id}", "200"), before + 2)

    def test_unmatched_paths_share_one_label(self):
        """
        404s on unknown paths collapse into a single bounded series.
        """
        before = _requests_total("GET", "unmatched", "404")

        self.client.get("/no/such/path/123")

        self.assertEqual(_requests_total("GET", "unmatched", "404"), before + 1)

    def test_unhandled_error_is_counted_as_500(self):
        """
        A handler crash is still recorded, as a 500.
        """
        before = _requests_total("GET", "/api/boom", "500")

        with self.assertLogs("app.api.observability", level="INFO"):
            response = self.client.get("/api/boom")

        self.assertEqual(response.status_code, 500)
        self.assertEqual(_requests_total("GET", "/api/boom", "500"), before + 1)

    def test_latency_is_observed(self):
        """
        Each request adds one observation to the latency histogram.
        """
        labels = {"method": "GET", "route": "/api/items/{item_id}"}
        before = REGISTRY.get_sample_value("hft_http_request_duration_seconds_count", labels) or 0

        self.client.get("/api/items/1")

        after = REGISTRY.get_sample_value("hft_http_request_duration_seconds_count", labels)
        self.assertEqual(after, before + 1)

    def test_unknown_methods_share_one_label(self):
        """
        Arbitrary verbs can't mint new label values.
        """
        before = _requests_total("OTHER", "unmatched", "404")

        self.client.request("PURGE", "/no/such/path")

        self.assertEqual(_requests_total("OTHER", "unmatched", "404"), before + 1)


class TestMetricsEndpoint(unittest.TestCase):
    def test_server_exposes_prometheus_metrics(self):
        """
        GET /metrics serves the text exposition format with the project's series.
        """
        from app.server import app

        client = TestClient(app)
        client.get("/health")

        response = client.get("/metrics")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.headers["content-type"].startswith("text/plain"))
        self.assertIn("hft_http_requests_total", response.text)
        self.assertIn("hft_sec_requests_total", response.text)
        self.assertIn('route="/health"', response.text)

    def test_server_returns_a_request_id(self):
        """
        The real app is wrapped by the middleware.
        """
        from app.server import app

        response = TestClient(app).get("/health")

        self.assertIn("X-Request-ID", response.headers)


class TestUvicornAccessLog(unittest.TestCase):
    @patch("uvicorn.run")
    @patch("app.main._frontend_sources_changed", return_value=False)
    @patch("pathlib.Path.exists", return_value=True)
    def test_uvicorn_access_log_is_disabled(self, _exists, _changed, mock_run):
        """
        The middleware's access line replaces uvicorn's, so requests aren't logged twice.
        """
        from app.main import run_server

        with patch.dict("os.environ", {"DOCKER_ENV": "1"}), patch("builtins.print"):
            run_server(host="127.0.0.1", port=8000)

        self.assertIs(mock_run.call_args.kwargs["access_log"], False)


if __name__ == "__main__":
    unittest.main()
