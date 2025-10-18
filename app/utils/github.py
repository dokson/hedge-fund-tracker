import os
import requests
from dotenv import load_dotenv

# Load variables from .env file
load_dotenv()


def open_issue(subject, body):
    """
    Creates an issue on GitHub if running in a GitHub Action, otherwise prints the alert to the console.

    Args:
        subject (str): The subject of the alert, which will become the Issue title.
        body (str): The body of the message/alert.
    """
    def print_error():
        """
        Prints the error to the console.
        """
        print(f"🚨 {subject}")
        print(body)

    # If not in a GitHub Action, just print to console and exit
    if os.getenv("GITHUB_ACTIONS") != "true":
        print_error()
        return

    # Running on GitHub
    token = os.getenv("GITHUB_TOKEN")
    repo = os.getenv("GITHUB_REPOSITORY")

    if not token or not repo:
        print("::error::❌ GITHUB_TOKEN or GITHUB_REPOSITORY not set in the Action environment.")
        print_error()
        return

    # Extract owner from repo string (e.g., 'owner/repo_name')
    repo_owner = repo.split('/')[0]

    url = f"https://api.github.com/repos/{repo}/issues"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
    }
    data = {
        "title": subject,
        "body": body,
        "labels": ["bug", "alert"],
        "assignees": [repo_owner]
    }

    try:
        response = requests.post(url, json=data, headers=headers)
        response.raise_for_status()

        if response.status_code == 201:
            print(f"::notice::✅ Successfully created GitHub Issue: {response.json()['html_url']}")
        else:
            # This case is unlikely if raise_for_status() is used, but good for robustness.
            print(f"::error::❌ Failed to create GitHub Issue with status code: {response.status_code}")
            print(f"Response: {response.text}")
            print_error()

    except requests.exceptions.RequestException as e:
        print(f"::error::❌ An exception occurred while creating GitHub Issue: {e}")
        print_error()
