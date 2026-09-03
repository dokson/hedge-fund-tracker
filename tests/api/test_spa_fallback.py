import unittest

from fastapi.testclient import TestClient

from app.api.paths import _FRONTEND_ROOT
from app.server import app

client = TestClient(app)


@unittest.skipUnless(
    (_FRONTEND_ROOT / "index.html").exists(), "frontend not built (app/frontend/dist missing)"
)
class TestSpaFallback(unittest.TestCase):
    """The catch-all must serve index.html for app routes only, never for assets.

    A stale hashed bundle answered with HTML leaves the page blank and shows no
    404 in the network log, so the miss has to surface as a real 404.
    """

    def test_missing_asset_is_404(self):
        """A hashed bundle that no longer exists 404s instead of returning HTML."""
        for path in (
            "/assets/index-OLDHASH.js",
            "/assets/index-OLDHASH.css",
            "/fonts/missing.woff2",
            "/logo-missing.png",
            "/favicon-999.png",
        ):
            with self.subTest(path=path):
                resp = client.get(path)
                self.assertEqual(resp.status_code, 404)
                self.assertNotIn("text/html", resp.headers.get("content-type", ""))

    def test_app_route_serves_index_html(self):
        """An extension-less route falls back to the SPA shell."""
        resp = client.get("/performance")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("text/html", resp.headers["content-type"])
        self.assertIn('<div id="root">', resp.text)

    def test_existing_asset_is_served_with_its_mime_type(self):
        """A real built asset is still served, with a JS (not HTML) content type."""
        bundles = sorted((_FRONTEND_ROOT / "assets").glob("*.js"))
        if not bundles:
            self.skipTest("no built JS bundle in app/frontend/dist/assets")
        resp = client.get(f"/assets/{bundles[0].name}")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("javascript", resp.headers["content-type"])

    def test_api_prefix_still_json_404(self):
        """Unknown /api/ paths keep their JSON 404."""
        resp = client.get("/api/does-not-exist")
        self.assertEqual(resp.status_code, 404)
        self.assertNotIn("text/html", resp.headers.get("content-type", ""))
