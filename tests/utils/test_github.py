import io
import os
import unittest
from unittest.mock import MagicMock, patch

from curl_cffi.requests.exceptions import RequestException

from app.utils.github import open_issue, raised_alerts


def _log_concat(captured) -> str:
    """
    Join captured log records into a single string for substring assertions.
    """
    return "\n".join(captured.output)


class TestGithub(unittest.TestCase):
    def setUp(self):
        """
        Silence workflow commands written straight to stdout.
        """
        stdout_patch = patch("sys.stdout", io.StringIO())
        stdout_patch.start()
        self.addCleanup(stdout_patch.stop)

    @patch("app.utils.github.requests.get")
    @patch("app.utils.github.requests.post")
    @patch("app.utils.github.os.getenv")
    def test_alert_creates_github_issue_successfully(self, mock_getenv, mock_post, mock_get):
        """
        Tests that a GitHub issue is created and a success annotation is emitted
        when running in a GitHub Action environment.
        """
        mock_getenv.side_effect = {
            "GITHUB_ACTIONS": "true",
            "GITHUB_TOKEN": "test_token",
            "GITHUB_REPOSITORY": "repo/hedge-fund-tracker",
        }.get

        mock_search_response = MagicMock()
        mock_search_response.json.return_value = {"total_count": 0}
        mock_get.return_value = mock_search_response

        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            "html_url": "https://github.com/repo/hedge-fund-tracker/issues/1"
        }
        mock_post.return_value = mock_response

        with self.assertLogs("app.utils.github", level="INFO") as cm:
            open_issue("Test Issue", "This is a test body.")

        mock_get.assert_called_once()
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        self.assertEqual(args[0], "https://api.github.com/repos/repo/hedge-fund-tracker/issues")
        self.assertEqual(kwargs["json"]["title"], "Test Issue")
        self.assertEqual(kwargs["json"]["assignees"], ["repo"])
        self.assertIn("Successfully created", _log_concat(cm))

    @patch("app.utils.github.requests.get")
    @patch("app.utils.github.os.getenv")
    def test_alert_does_not_create_duplicate_issue(self, mock_getenv, mock_get):
        """
        Tests that a new issue is NOT created if one with the same title already exists.
        """
        mock_getenv.side_effect = {
            "GITHUB_ACTIONS": "true",
            "GITHUB_TOKEN": "test_token",
            "GITHUB_REPOSITORY": "repo/hedge-fund-tracker",
        }.get

        mock_search_response = MagicMock()
        mock_search_response.json.return_value = {
            "total_count": 1,
            "items": [{"html_url": "https://github.com/repo/hedge-fund-tracker/issues/existing"}],
        }
        mock_get.return_value = mock_search_response

        with self.assertLogs("app.utils.github", level="INFO") as cm:
            open_issue("Existing Issue", "This should not be created again.")

        mock_get.assert_called_once()
        self.assertIn("Issue already exists", _log_concat(cm))

    @patch("app.utils.github.os.getenv")
    def test_alert_prints_to_console_locally(self, mock_getenv):
        """
        Tests that the alert is logged when not in a GitHub Action environment.
        """
        mock_getenv.return_value = "false"

        with self.assertLogs("app.utils.github", level="INFO") as cm:
            open_issue("Local Test Alert", "This is a local test body.")

        joined = _log_concat(cm)
        self.assertIn("Local Test Alert", joined)
        self.assertIn("This is a local test body.", joined)

    @patch("app.utils.github.requests.post")
    @patch("app.utils.github.os.getenv")
    def test_alert_handles_missing_github_token(self, mock_getenv, mock_post):
        """
        Tests that an error and the alert are logged if GITHUB_TOKEN is missing.
        """
        mock_getenv.side_effect = {
            "GITHUB_ACTIONS": "true",
            "GITHUB_REPOSITORY": "repo/hedge-fund-tracker",
        }.get

        with self.assertLogs("app.utils.github", level="INFO") as cm:
            open_issue("Subject", "Body")

        mock_post.assert_not_called()
        joined = _log_concat(cm)
        self.assertIn("GITHUB_TOKEN", joined)
        self.assertIn("Subject", joined)
        self.assertIn("Body", joined)

    @patch("app.utils.github.requests.get")
    @patch("app.utils.github.os.getenv")
    def test_search_query_escapes_quotes_in_subject(self, mock_getenv, mock_get):
        """
        A subject containing a double-quote must be escaped in the search
        qualifier ``in:title "..."`` so it can't break out and alter the
        filter semantics (potential false-negative on dup detection or false
        match on an unrelated issue).
        """
        mock_getenv.side_effect = {
            "GITHUB_ACTIONS": "true",
            "GITHUB_TOKEN": "test_token",
            "GITHUB_REPOSITORY": "repo/hedge-fund-tracker",
        }.get

        mock_search_response = MagicMock()
        mock_search_response.json.return_value = {
            "total_count": 1,
            "items": [{"html_url": "https://github.com/repo/hedge-fund-tracker/issues/1"}],
        }
        mock_get.return_value = mock_search_response

        with self.assertLogs("app.utils.github", level="INFO"):
            open_issue('Fund "Special" LLC anomaly', "body")

        args, kwargs = mock_get.call_args
        query = kwargs["params"]["q"]
        # The escaped `\"` must be present; a bare `"` after `in:title "` (other
        # than the wrapping ones) would be a closing-quote injection.
        self.assertIn('in:title "Fund \\"Special\\" LLC anomaly"', query)

    @patch("app.utils.github.requests.get")
    @patch("app.utils.github.requests.post")
    @patch("app.utils.github.os.getenv")
    def test_malformed_github_repository_is_rejected(self, mock_getenv, mock_post, mock_get):
        """
        ``GITHUB_REPOSITORY`` must be ``owner/name``. Anything else (empty,
        single segment, three segments) is rejected before any API call.
        """
        mock_getenv.side_effect = {
            "GITHUB_ACTIONS": "true",
            "GITHUB_TOKEN": "test_token",
            "GITHUB_REPOSITORY": "no-slash",  # malformed
        }.get

        with self.assertLogs("app.utils.github", level="ERROR") as cm:
            open_issue("Subject", "Body")

        mock_get.assert_not_called()
        mock_post.assert_not_called()
        self.assertIn("malformed", _log_concat(cm).lower())

    @patch("app.utils.github.requests.get")
    @patch("app.utils.github.requests.post")
    @patch("app.utils.github.os.getenv")
    def test_sends_bearer_authorization_and_user_agent(self, mock_getenv, mock_post, mock_get):
        """
        Both calls use the ``Bearer`` scheme (GitHub's recommendation for PATs)
        and set a User-Agent: GitHub's REST API rejects requests without one
        (HTTP 403) and curl_cffi sends none by default.
        """
        mock_getenv.side_effect = {
            "GITHUB_ACTIONS": "true",
            "GITHUB_TOKEN": "test_token",
            "GITHUB_REPOSITORY": "repo/hedge-fund-tracker",
        }.get

        mock_search_response = MagicMock()
        mock_search_response.json.return_value = {"total_count": 0}
        mock_get.return_value = mock_search_response

        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"html_url": "https://example.com/i/1"}
        mock_post.return_value = mock_response

        with self.assertLogs("app.utils.github", level="INFO"):
            open_issue("Subject", "Body")

        for call in (mock_get.call_args, mock_post.call_args):
            self.assertEqual(call.kwargs["headers"]["Authorization"], "Bearer test_token")
            self.assertTrue(call.kwargs["headers"].get("User-Agent"))

    @patch("app.utils.github.requests.get")
    @patch("app.utils.github.requests.post")
    @patch("app.utils.github.os.getenv")
    def test_retries_without_assignees_when_owner_is_not_assignable(
        self, mock_getenv, mock_post, mock_get
    ):
        """
        Org-owned repos can't assign the org account itself, so GitHub returns
        422. The function must retry the POST without the ``assignees`` field
        so the alert is still filed.
        """
        mock_getenv.side_effect = {
            "GITHUB_ACTIONS": "true",
            "GITHUB_TOKEN": "test_token",
            "GITHUB_REPOSITORY": "my-org/hedge-fund-tracker",
        }.get

        mock_search_response = MagicMock()
        mock_search_response.json.return_value = {"total_count": 0}
        mock_get.return_value = mock_search_response

        # First POST: 422 (assignee not assignable). Second POST (retry): 201.
        first = MagicMock()
        first.status_code = 422
        second = MagicMock()
        second.status_code = 201
        second.json.return_value = {"html_url": "https://example.com/i/1"}
        mock_post.side_effect = [first, second]

        with self.assertLogs("app.utils.github", level="INFO"):
            open_issue("Org-owned alert", "Body")

        self.assertEqual(mock_post.call_count, 2)
        first_body = mock_post.call_args_list[0].kwargs["json"]
        second_body = mock_post.call_args_list[1].kwargs["json"]
        self.assertIn("assignees", first_body)
        self.assertNotIn("assignees", second_body)
        # Title and body persist across the retry so the alert content is intact.
        self.assertEqual(second_body["title"], "Org-owned alert")
        self.assertEqual(second_body["body"], "Body")

    @patch("app.utils.github.requests.get")
    @patch("app.utils.github.requests.post")
    @patch("app.utils.github.os.getenv")
    def test_alert_handles_api_error(self, mock_getenv, mock_post, mock_get):
        """
        Tests that an error is logged and the alert falls back to logging when the API call fails.
        """
        mock_getenv.side_effect = {
            "GITHUB_ACTIONS": "true",
            "GITHUB_TOKEN": "test_token",
            "GITHUB_REPOSITORY": "repo/hedge-fund-tracker",
        }.get

        mock_search_response = MagicMock()
        mock_search_response.json.return_value = {"total_count": 0}
        mock_get.return_value = mock_search_response

        mock_post.side_effect = RequestException("API is down")

        with self.assertLogs("app.utils.github", level="INFO") as cm:
            open_issue("API Error Test", "This should be logged as a fallback.")

        mock_get.assert_called_once()
        mock_post.assert_called_once()
        joined = _log_concat(cm)
        self.assertIn("An exception occurred while creating GitHub Issue", joined)
        self.assertIn("API Error Test", joined)
        self.assertIn("This should be logged as a fallback.", joined)


class TestWorkflowCommands(unittest.TestCase):
    """
    GitHub only parses workflow commands that start at the beginning of a stdout line.
    """

    _ENV = {
        "GITHUB_ACTIONS": "true",
        "GITHUB_TOKEN": "test_token",
        "GITHUB_REPOSITORY": "repo/hedge-fund-tracker",
    }

    def test_fake_getenv_leaves_other_variables_to_the_real_environment(self):
        """
        Patching os.getenv patches it process-wide: a test runner reading its own
        variables mid-test (VS Code's TEST_RUN_PIPE) must still see them.
        """
        with patch.dict(os.environ, {"HFT_TEST_PROBE": "real"}):
            self.assertEqual(self._fake_getenv("HFT_TEST_PROBE"), "real")
        self.assertEqual(self._fake_getenv("GITHUB_TOKEN"), "test_token")
        self.assertIsNone(self._fake_getenv("GITHUB_UNSET_FOR_TEST"))

    @classmethod
    def _fake_getenv(cls, key, default=None):
        """
        The GitHub variables from _ENV; anything else from the real environment.
        """
        if key.startswith("GITHUB_"):
            return cls._ENV.get(key, default)
        return os.environ.get(key, default)

    def _run(self, mock_getenv, subject="Subject", body="Body"):
        """
        Run open_issue with stdout captured and return the captured text and log records.
        """
        mock_getenv.side_effect = self._fake_getenv
        buf = io.StringIO()
        with patch("sys.stdout", buf), self.assertLogs("app.utils.github", level="INFO") as cm:
            self.assertIsNotNone(os.getenv("PATH"), "a runner's own variables must stay readable")
            open_issue(subject, body)
        return buf.getvalue(), _log_concat(cm)

    @patch("app.utils.github.requests.get")
    @patch("app.utils.github.requests.post")
    @patch("app.utils.github.os.getenv")
    def test_notice_is_written_at_line_start(self, mock_getenv, mock_post, mock_get):
        """
        A created issue emits a ::notice:: command at column zero, with no emoji marker.
        """
        mock_get.return_value.json.return_value = {"total_count": 0}
        mock_post.return_value.status_code = 201
        mock_post.return_value.json.return_value = {"html_url": "https://example.com/i/1"}

        out, logs = self._run(mock_getenv)

        lines = out.splitlines()
        self.assertTrue(any(line.startswith("::notice::") for line in lines), out)
        self.assertNotIn("✅", out)
        self.assertNotIn("::notice::", logs)
        self.assertIn("Successfully created", logs)

    @patch("app.utils.github.requests.get")
    @patch("app.utils.github.requests.post")
    @patch("app.utils.github.os.getenv")
    def test_error_is_written_at_line_start(self, mock_getenv, mock_post, mock_get):
        """
        A failed create emits a ::error:: command at column zero, with no emoji marker.
        """
        mock_get.return_value.json.return_value = {"total_count": 0}
        mock_post.side_effect = RequestException("down")

        out, _ = self._run(mock_getenv)

        lines = out.splitlines()
        self.assertTrue(any(line.startswith("::error::") for line in lines), out)
        self.assertNotIn("❌", out)

    @patch("app.utils.github.requests.get")
    @patch("app.utils.github.os.getenv")
    def test_command_message_newlines_are_escaped(self, mock_getenv, mock_get):
        """
        A newline in an interpolated value must not split the workflow command.
        """
        mock_get.return_value.json.return_value = {
            "total_count": 1,
            "items": [{"html_url": "https://example.com/i/1\n::error::forged"}],
        }

        out, _ = self._run(mock_getenv)

        self.assertFalse(any(line.startswith("::error::") for line in out.splitlines()), out)

    @patch("app.utils.github.requests.get")
    @patch("app.utils.github.requests.post")
    @patch("app.utils.github.os.getenv")
    def test_malformed_search_response_degrades_gracefully(self, mock_getenv, mock_post, mock_get):
        """
        A search body that is not JSON, or lacks the expected keys, must not crash the run.
        """
        for json_behaviour in (ValueError("not json"), {"unexpected": 1}, {"total_count": 1}):
            with self.subTest(json_behaviour=json_behaviour):
                mock_post.reset_mock()
                if isinstance(json_behaviour, Exception):
                    mock_get.return_value.json.side_effect = json_behaviour
                else:
                    mock_get.return_value.json.side_effect = None
                    mock_get.return_value.json.return_value = json_behaviour

                out, logs = self._run(mock_getenv, subject="Malformed")

                mock_post.assert_not_called()
                self.assertIn("Malformed", logs)
                self.assertTrue(any(line.startswith("::error::") for line in out.splitlines()))


class TestRaisedAlerts(unittest.TestCase):
    @patch("app.utils.github.os.getenv", return_value=None)
    def test_open_issue_records_the_subject(self, _mock_getenv):
        """
        Every alert raised in the process is recorded for the run summary.
        """
        with self.assertLogs("app.utils.github", level="WARNING"):
            open_issue("Ticker not found for CUSIP 'TEST00001'", "body")

        self.assertIn("Ticker not found for CUSIP 'TEST00001'", raised_alerts())


if __name__ == "__main__":
    unittest.main()
