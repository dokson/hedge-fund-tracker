from app.utils.github import open_issue
import requests
import unittest
from unittest.mock import MagicMock, call, patch


class TestGithub(unittest.TestCase):
    @patch('app.utils.github.requests.get')
    @patch('app.utils.github.requests.post')
    @patch('builtins.print')
    @patch('app.utils.github.os.getenv')
    def test_alert_creates_github_issue_successfully(self, mock_getenv, mock_print, mock_post, mock_get):
        """
        Tests that a GitHub issue is created and a success message is printed
        when running in a GitHub Action environment.
        """
        # Mock environment variables
        mock_getenv.side_effect = {
            "GITHUB_ACTIONS": "true",
            "GITHUB_TOKEN": "test_token",
            "GITHUB_REPOSITORY": "repo/hedge-fund-tracker"
        }.get

        # Mock the response from requests.get (search for existing issue)
        mock_search_response = MagicMock()
        mock_search_response.json.return_value = {"total_count": 0}
        mock_get.return_value = mock_search_response

        # Mock the response from requests.post
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"html_url": "https://github.com/repo/hedge-fund-tracker/issues/1"}
        mock_post.return_value = mock_response

        subject = "Test Issue"
        body = "This is a test body."
        open_issue(subject, body)

        # Assert that requests.get was called for the search
        mock_get.assert_called_once()

        # Assert that requests.post was called correctly
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        self.assertEqual(args[0], "https://api.github.com/repos/repo/hedge-fund-tracker/issues") # create_url
        self.assertEqual(kwargs['json']['title'], subject)
        self.assertEqual(kwargs['json']['assignees'], ['repo'])

        # Assert that the success message was printed and the fallback was not
        mock_print.assert_called_once_with("::notice::✅ Successfully created GitHub Issue: https://github.com/repo/hedge-fund-tracker/issues/1")


    @patch('app.utils.github.requests.get')
    @patch('builtins.print')
    @patch('app.utils.github.os.getenv')
    def test_alert_does_not_create_duplicate_issue(self, mock_getenv, mock_print, mock_get):
        """
        Tests that a new issue is NOT created if one with the same title already exists.
        """
        # Mock environment variables
        mock_getenv.side_effect = {
            "GITHUB_ACTIONS": "true",
            "GITHUB_TOKEN": "test_token",
            "GITHUB_REPOSITORY": "repo/hedge-fund-tracker"
        }.get

        # Mock the response from requests.get to simulate an existing issue
        mock_search_response = MagicMock()
        mock_search_response.json.return_value = {
            "total_count": 1,
            "items": [{"html_url": "https://github.com/repo/hedge-fund-tracker/issues/existing"}]
        }
        mock_get.return_value = mock_search_response

        subject = "Existing Issue"
        body = "This should not be created again."
        open_issue(subject, body)

        # Assert that requests.get was called for the search
        mock_get.assert_called_once()

        # Assert that the notice for an existing issue was printed
        mock_print.assert_called_once_with("::notice::✅ Issue already exists: https://github.com/repo/hedge-fund-tracker/issues/existing")


    @patch('builtins.print')
    @patch('app.utils.github.os.getenv')
    def test_alert_prints_to_console_locally(self, mock_getenv, mock_print):
        """
        Tests that the alert is printed to the console when not in a GitHub Action environment.
        """
        # Mock os.getenv to simulate a local environment
        mock_getenv.return_value = "false"

        subject = "Local Test Alert"
        body = "This is a local test body."
        open_issue(subject, body)

        # Check that print was called with the subject and body
        expected_calls = [
            call(f"🚨 {subject}"),
            call(body)
        ]
        mock_print.assert_has_calls(expected_calls)


    @patch('app.utils.github.requests.post')
    @patch('builtins.print')
    @patch('app.utils.github.os.getenv')
    def test_alert_handles_missing_github_token(self, mock_getenv, mock_print, mock_post):
        """
        Tests that an error and the alert are printed if GITHUB_TOKEN is missing.
        """
        mock_getenv.side_effect = {
            "GITHUB_ACTIONS": "true",
            "GITHUB_REPOSITORY": "repo/hedge-fund-tracker"
        }.get

        subject = "Subject"
        body = "Body"
        open_issue(subject, body)

        # Assert that no API call was made
        mock_post.assert_not_called()
        # Assert that an error message and the fallback alert were printed
        expected_calls = [
            call("::error::❌ GITHUB_TOKEN or GITHUB_REPOSITORY not set in the Action environment."),
            call(f"🚨 {subject}"),
            call(body)
        ]
        mock_print.assert_has_calls(expected_calls)


    @patch('app.utils.github.requests.get')
    @patch('app.utils.github.requests.post')
    @patch('builtins.print')
    @patch('app.utils.github.os.getenv')
    def test_alert_handles_api_error(self, mock_getenv, mock_print, mock_post, mock_get):
        """
        Tests that an error and the alert are printed if the GitHub API call fails.
        """
        mock_getenv.side_effect = {
            "GITHUB_ACTIONS": "true",
            "GITHUB_TOKEN": "test_token",
            "GITHUB_REPOSITORY": "repo/hedge-fund-tracker"
        }.get

        # Mock the response from requests.get (search for existing issue)
        mock_search_response = MagicMock()
        mock_search_response.json.return_value = {"total_count": 0}
        mock_get.return_value = mock_search_response

        # Mock a failed response from requests.post
        mock_post.side_effect = requests.exceptions.RequestException("API is down")

        subject = "API Error Test"
        body = "This should be printed as a fallback."
        open_issue(subject, body)

        # Assert that the search call was attempted
        mock_get.assert_called_once()
        # Assert that the API call was attempted
        mock_post.assert_called_once()
        # Assert that an error message and the fallback alert were printed
        expected_calls = [
            call("::error::❌ An exception occurred while creating GitHub Issue: API is down"),
            call(f"🚨 {subject}"),
            call(body)
        ]
        mock_print.assert_has_calls(expected_calls, any_order=False)


if __name__ == '__main__':
    unittest.main()
