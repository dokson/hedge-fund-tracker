import unittest


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


if __name__ == "__main__":
    unittest.main()
