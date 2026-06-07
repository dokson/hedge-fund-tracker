"""
PreToolUse hook: enforces that Python tooling (tests, typecheck, lint) runs
inside the pipenv virtualenv for this repo.

Background: the system Python on this dev machine lacks pandas-stubs/fastapi_users,
so running tests or pyright against it generates noise/false errors. The pipenv
venv has the correct dependencies.

Behavior: reads the hook JSON on stdin. If the proposed Bash/PowerShell command
invokes `python -m unittest|pytest|mypy|ruff|pyright` or bare `pyright|ruff|
mypy|pytest` WITHOUT a `pipenv run` (or `python -m pipenv run`) prefix
upstream, emit a deny decision with a fix-up hint. Otherwise stay silent so
the command runs normally.
"""

from __future__ import annotations

import json
import re
import sys

# Command is allowed if any occurrence of `pipenv run` is upstream of the tool.
_ALLOWED_PREFIX = re.compile(r"\b(?:pipenv\s+run|python\s+-m\s+pipenv\s+run)\b")

# Package-manager invocations: when the line is installing/managing packages,
# tool names appear as positional package arguments (e.g. `pipenv install pyright`)
# and must not be confused with tool invocations.
_PKG_MANAGER = re.compile(
    r"\b(?:pip(?:env)?|uv|poetry|conda)\s+(?:install|uninstall|add|remove|update|lock|sync|run-shell)\b"
    r"|\bpython\s+-m\s+(?:pip|pipenv|uv|poetry)\b"
)

# Block patterns: ``python -m {unittest|pytest|mypy|ruff|pyright}`` and bare
# invocations of those tools at a command boundary.
_PYTHON_M = re.compile(r"\bpython(?:[0-9.]*)\s+-m\s+(?:unittest|pytest|mypy|ruff|pyright)\b")
_BARE_TOOL = re.compile(r"(?:^|[\s;&|`])(?:pyright|ruff|mypy|pytest)\b")


def main() -> None:
    """
    Decide whether to allow the proposed tool call; emit JSON if denying.
    """
    try:
        payload = json.load(sys.stdin)
    except Exception:
        # If we can't parse the hook payload, fail open — never block on bugs.
        return

    cmd = payload.get("tool_input", {}).get("command", "") or ""

    if _ALLOWED_PREFIX.search(cmd):
        return

    # Skip package-manager invocations — pyright/ruff/etc. appearing as
    # positional args to `pipenv install`, `pip install`, etc. are NOT tool calls.
    if _PKG_MANAGER.search(cmd):
        return

    # Strip string-literal contents (single- and double-quoted) so the pattern
    # matchers don't see "pyright"/"ruff"/etc. when they appear as data inside
    # `grep "pattern"`, `Select-String "pattern"`, etc.
    stripped = re.sub(r"'[^']*'|\"[^\"]*\"", "", cmd)

    if not (_PYTHON_M.search(stripped) or _BARE_TOOL.search(stripped)):
        return

    message = (
        "Python tooling in this repo must run through the pipenv virtualenv. "
        "Retry the command prefixed with `python -m pipenv run` "
        "(e.g. `python -m pipenv run python -m unittest discover tests`). "
        "See AGENTS.md > 'Running Python tooling' for the rationale."
    )

    sys.stdout.write(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": message,
                }
            }
        )
    )


if __name__ == "__main__":
    main()
