import unittest
from unittest.mock import MagicMock, patch

from curl_cffi.requests.exceptions import RequestException

from app.utils.github import open_issue


def _log_concat(captured) -> str:
    """
    Join captured log records into a single string for substring assertions.
    """
    return "\n".join(captured.output)


class TestGithub(unittest.TestCase):
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
        self.assertIn("::notice::", _log_concat(cm))
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
    def test_uses_bearer_authorization_scheme(self, mock_getenv, mock_post, mock_get):
        """
        Authorization header must use the ``Bearer`` scheme (GitHub's
        recommendation for PATs since 2022). The legacy ``token`` scheme
        still works but is deprecated for fine-grained PATs.
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


if __name__ == "__main__":
    unittest.main()
