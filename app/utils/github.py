import os

from curl_cffi import requests
from curl_cffi.requests.exceptions import RequestException
from dotenv import load_dotenv

from app.utils.logger import get_logger, log_safe

logger = get_logger(__name__)

GITHUB_API_TIMEOUT_S = 10

_dotenv_loaded = False


def _ensure_dotenv() -> None:
    """
    Load ``.env`` once on first call instead of at import time.

    Avoids mutating ``os.environ`` as a side effect of importing this module —
    test fixtures using ``monkeypatch.delenv`` / ``patch.dict("os.environ")``
    behave predictably regardless of import order.
    """
    global _dotenv_loaded
    if not _dotenv_loaded:
        load_dotenv()
        _dotenv_loaded = True


def _split_repo(repo: str | None) -> tuple[str, str] | None:
    """
    Validate and split ``GITHUB_REPOSITORY`` into ``(owner, name)``.

    Returns ``None`` on missing or malformed values (empty string, wrong number
    of segments, empty segment). Prevents downstream calls from receiving a
    truncated path like ``/repos//issues`` or an empty ``assignees`` value.
    """
    if not repo:
        return None
    parts = repo.split("/")
    if len(parts) != 2 or not all(parts):
        return None
    return parts[0], parts[1]


def _escape_search_qualifier(value: str) -> str:
    """
    Escape a value embedded inside a GitHub search qualifier (``in:title "..."``).

    Backslashes are doubled and double-quotes escaped so a subject like
    ``O'Brien "Capital" LLC`` can't break out of the quoted title segment
    and alter the filter semantics.
    """
    return value.replace("\\", "\\\\").replace('"', '\\"')


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
        logger.warning("%s", log_safe(subject, max_len=200))
        logger.info(body)

    _ensure_dotenv()

    # If not in a GitHub Action, just print to console and exit
    if os.getenv("GITHUB_ACTIONS") != "true":
        print_error()
        return

    # Running on GitHub
    token = os.getenv("GITHUB_TOKEN")
    repo = os.getenv("GITHUB_REPOSITORY")

    if not token:
        logger.info(
            "::error::❌ GITHUB_TOKEN or GITHUB_REPOSITORY not set in the Action environment."
        )
        print_error()
        return

    split = _split_repo(repo)
    if split is None:
        logger.error(
            "::error::❌ GITHUB_REPOSITORY missing or malformed (expected 'owner/name', got %r).",
            repo,
        )
        print_error()
        return
    repo_owner, _repo_name = split

    headers = {
        # Bearer is the form GitHub recommends for PATs and fine-grained tokens
        # since 2022; `token` still works but is deprecated for the latter.
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.v3+json",
    }

    try:
        # Check if an issue with the same title already exists. Escape `"` and
        # `\` in the subject so a title containing quotes can't break out of
        # the `in:title "..."` qualifier and alter the search semantics.
        safe_subject = _escape_search_qualifier(subject)
        search_url = "https://api.github.com/search/issues"
        query = f'repo:{repo} is:issue is:open in:title "{safe_subject}"'
        params = {"q": query}
        search_response = requests.get(
            search_url, headers=headers, params=params, timeout=GITHUB_API_TIMEOUT_S
        )
        search_response.raise_for_status()
        search_results = search_response.json()

        if search_results["total_count"] > 0:
            issue_url = search_results["items"][0]["html_url"]
            logger.info("::notice::✅ Issue already exists: %s", issue_url)
            return

        # If no existing issue is found, create a new one
        create_url = f"https://api.github.com/repos/{repo}/issues"

    except RequestException:
        logger.error(
            "::error::❌ An exception occurred while searching for GitHub Issue", exc_info=True
        )
        print_error()
        return

    data = {"title": subject, "body": body, "labels": ["bug", "alert"], "assignees": [repo_owner]}

    try:
        response = requests.post(
            create_url, json=data, headers=headers, timeout=GITHUB_API_TIMEOUT_S
        )

        # On org-owned repos the owner segment is the organisation, which
        # cannot be assigned. GitHub returns 422 in that case (and for any
        # other unassignable account: archived users, disabled SSO seats).
        # Drop assignees and retry once so the alert is still filed.
        if response.status_code == 422 and "assignees" in data:
            data_no_assignees = {k: v for k, v in data.items() if k != "assignees"}
            response = requests.post(
                create_url, json=data_no_assignees, headers=headers, timeout=GITHUB_API_TIMEOUT_S
            )

        response.raise_for_status()

        if response.status_code == 201:
            logger.info(
                "::notice::✅ Successfully created GitHub Issue: %s", response.json()["html_url"]
            )
        else:
            # Unlikely after raise_for_status(); body intentionally not logged to avoid
            # leaking API diagnostics into CI logs.
            logger.error(
                "::error::❌ Failed to create GitHub Issue with status code: %s",
                response.status_code,
            )
            print_error()

    except RequestException:
        logger.error("::error::❌ An exception occurred while creating GitHub Issue", exc_info=True)
        print_error()
