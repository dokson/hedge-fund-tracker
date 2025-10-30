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

    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
    }

    try:
        # Check if an issue with the same title already exists
        search_url = "https://api.github.com/search/issues"
        query = f'repo:{repo} is:issue is:open in:title "{subject}"'
        params = {"q": query}
        search_response = requests.get(search_url, headers=headers, params=params)
        search_response.raise_for_status()
        search_results = search_response.json()

        if search_results["total_count"] > 0:
            issue_url = search_results["items"][0]["html_url"]
            print(f"::notice::✅ Issue already exists: {issue_url}")
            return

        # If no existing issue is found, create a new one
        repo_owner = repo.split('/')[0]
        create_url = f"https://api.github.com/repos/{repo}/issues"

    except requests.exceptions.RequestException as e:
        print(f"::error::❌ An exception occurred while searching for GitHub Issue: {e}")
        print_error()
        return

    data = {
        "title": subject,
        "body": body,
        "labels": ["bug", "alert"],
        "assignees": [repo_owner]
    }

    try:
        response = requests.post(create_url, json=data, headers=headers)
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
