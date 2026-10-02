"""
Pre-shell hook shared by every coding agent: Python tooling (tests, type
checks, lint) must run inside this repo's pipenv virtualenv, because the system
Python lacks the stubs and packages and produces false errors.

Reads the agent's hook JSON on stdin and answers in that agent's contract,
selected with `--format`. Wired up by scripts/sync_agent_configs.py.
"""

from __future__ import annotations

import argparse
import json
import re
import sys

_ALLOWED_PREFIX = re.compile(r"\b(?:pipenv\s+run|python\s+-m\s+pipenv\s+run)\b")

# Tool names given as package arguments (`pipenv install pyright`) are not invocations.
_PKG_MANAGER = re.compile(
    r"\b(?:pip(?:env)?|uv|poetry|conda)\s+(?:install|uninstall|add|remove|update|upgrade|lock|sync|run-shell)\b"
    r"|\bpython\s+-m\s+(?:pip|pipenv|uv|poetry)\b"
)

_PYTHON_M = re.compile(r"\bpython(?:[0-9.]*)\s+-m\s+(?:unittest|pytest|mypy|ruff|pyright)\b")
_BARE_TOOL = re.compile(r"(?:^|[\s;&|`])(?:pyright|ruff|mypy|pytest)\b")

_MESSAGE = (
    "Python tooling in this repo must run through the pipenv virtualenv. "
    "Retry the command prefixed with `python -m pipenv run` "
    "(e.g. `python -m pipenv run python -m unittest discover tests`). "
    "See AGENTS.md > 'Running Python tooling' for the rationale."
)

FORMATS = ("claude", "codex", "gemini", "cursor")


def is_blocked(command: str) -> bool:
    """
    Return True when the shell command runs Python tooling outside pipenv.
    """
    if _ALLOWED_PREFIX.search(command) or _PKG_MANAGER.search(command):
        return False
    # Quoted text is data (`grep "pyright"`), not an invocation.
    stripped = re.sub(r"'[^']*'|\"[^\"]*\"", "", command)
    return bool(_PYTHON_M.search(stripped) or _BARE_TOOL.search(stripped))


def _command_from(payload: object) -> str:
    """
    Extract the shell command from either payload shape: Claude Code, Codex and
    Gemini nest it under `tool_input`, Cursor sends it at the top level.
    """
    if not isinstance(payload, dict):
        return ""
    tool_input = payload.get("tool_input")
    if isinstance(tool_input, dict) and isinstance(tool_input.get("command"), str):
        return tool_input["command"]
    command = payload.get("command")
    return command if isinstance(command, str) else ""


def _decision(fmt: str, blocked: bool) -> dict[str, object] | None:
    """
    Build the agent-specific response; None means "say nothing" (allow).
    """
    if fmt == "cursor":
        if not blocked:
            return {"permission": "allow"}
        return {"permission": "deny", "user_message": _MESSAGE, "agent_message": _MESSAGE}
    if not blocked:
        return None
    if fmt == "gemini":
        return {"decision": "deny", "reason": _MESSAGE}
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": _MESSAGE,
        }
    }


def main(argv: list[str] | None = None) -> int:
    """
    Read the hook payload, classify its command and print the decision.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--format", choices=FORMATS, default="claude")
    fmt = parser.parse_args(argv).format
    try:
        payload = json.load(sys.stdin)
    except ValueError:
        # Fail open: a hook bug must never block the agent.
        return 0
    response = _decision(fmt, is_blocked(_command_from(payload)))
    if response is not None:
        sys.stdout.write(json.dumps(response))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
