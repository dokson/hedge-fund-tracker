import os
import sys
import threading

from curl_cffi import requests
from curl_cffi.requests.exceptions import RequestException
from dotenv import load_dotenv

from app.utils.logger import get_logger, log_safe

logger = get_logger(__name__)

GITHUB_API_TIMEOUT_S = 10

_dotenv_loaded = False

_raised_alerts: list[str] = []
_raised_alerts_lock = threading.Lock()


def raised_alerts() -> list[str]:
    """
    Subjects of every alert raised by ``open_issue`` in this process, oldest first.
    """
    with _raised_alerts_lock:
        return list(_raised_alerts)


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


def _workflow_command(kind: str, message: str) -> None:
    """
    Emit a GitHub Actions workflow command (``::error::`` / ``::notice::``) on stdout.

    The message is escaped per the runner's rules so an interpolated newline
    cannot split the command or forge a second one.
    """
    escaped = message.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
    # The runner only parses commands at column zero, which the logger's prefix breaks.
    sys.stdout.write(f"::{kind}::{escaped}\n")
    sys.stdout.flush()


def _report(kind: str, message: str, *, exc_info: bool = False) -> None:
    """
    Log a human-readable message and mirror it as a workflow annotation.
    """
    if kind == "error":
        logger.error(message, exc_info=exc_info)
    else:
        logger.success(message)
    _workflow_command(kind, message)


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

    with _raised_alerts_lock:
        _raised_alerts.append(subject)
    _ensure_dotenv()

    # If not in a GitHub Action, just print to console and exit
    if os.getenv("GITHUB_ACTIONS") != "true":
        print_error()
        return

    # Running on GitHub
    token = os.getenv("GITHUB_TOKEN")
    repo = os.getenv("GITHUB_REPOSITORY")

    if not token:
        _report("error", "GITHUB_TOKEN not set in the Action environment.")
        print_error()
        return

    split = _split_repo(repo)
    if split is None:
        _report(
            "error",
            f"GITHUB_REPOSITORY missing or malformed (expected 'owner/name', got {log_safe(repo)!r}).",
        )
        print_error()
        return
    repo_owner, repo_name = split

    headers = {
        # Bearer is the form GitHub recommends for PATs and fine-grained tokens
        # since 2022; `token` still works but is deprecated for the latter.
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.v3+json",
        # GitHub rejects requests without a User-Agent (403); curl_cffi sends none.
        "User-Agent": repo_name,
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
            _report("notice", f"Issue already exists: {log_safe(issue_url, max_len=200)}")
            return

        # If no existing issue is found, create a new one
        create_url = f"https://api.github.com/repos/{repo}/issues"

    except RequestException:
        _report("error", "An exception occurred while searching for GitHub Issue", exc_info=True)
        print_error()
        return
    except ValueError, KeyError, IndexError, TypeError:
        _report("error", "Malformed GitHub search response; issue not filed", exc_info=True)
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
            issue_url = response.json().get("html_url", "")
            _report(
                "notice", f"Successfully created GitHub Issue: {log_safe(issue_url, max_len=200)}"
            )
        else:
            # Unlikely after raise_for_status(); body intentionally not logged to avoid
            # leaking API diagnostics into CI logs.
            _report(
                "error", f"Failed to create GitHub Issue with status code: {response.status_code}"
            )
            print_error()

    except RequestException, ValueError, AttributeError:
        _report("error", "An exception occurred while creating GitHub Issue", exc_info=True)
        print_error()
