"""
Tests for the tool-agnostic agent hook in .agents/hooks/enforce_pipenv.py.
"""

import importlib.util
import io
import json
import unittest
from pathlib import Path
from unittest.mock import patch

_HOOK_PATH = Path(__file__).resolve().parents[1] / ".agents" / "hooks" / "enforce_pipenv.py"


def _load_hook():
    """
    Import the hook module from its path, since `.agents` is not a package name.
    """
    spec = importlib.util.spec_from_file_location("enforce_pipenv", _HOOK_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run(payload: object, fmt: str) -> tuple[str, int]:
    """
    Run the hook on a JSON payload and return its stdout and exit code.
    """
    hook = _load_hook()
    stdout = io.StringIO()
    stdin = io.StringIO(payload if isinstance(payload, str) else json.dumps(payload))
    with patch("sys.stdin", stdin), patch("sys.stdout", stdout):
        code = hook.main(["--format", fmt])
    return stdout.getvalue(), code


class TestIsBlocked(unittest.TestCase):
    """
    The command classifier shared by every agent format.
    """

    def test_blocks_bare_and_module_invocations(self):
        """
        Bare tool names and `python -m <tool>` outside pipenv are blocked.
        """
        hook = _load_hook()
        for cmd in ["pyright", "ruff check .", "python -m unittest discover", "cd x && pytest"]:
            with self.subTest(cmd=cmd):
                self.assertTrue(hook.is_blocked(cmd))

    def test_allows_pipenv_package_managers_and_quoted_data(self):
        """
        pipenv-prefixed runs, package installs and quoted search patterns pass.
        """
        hook = _load_hook()
        for cmd in [
            "py -3.14 -m pipenv run pyright",
            "pipenv run python -m unittest",
            "pipenv install --dev ruff",
            "py -3.14 -m pipenv upgrade --dev ruff==0.16.10",
            'grep -rn "pyright" .',
            "npm test",
            "",
        ]:
            with self.subTest(cmd=cmd):
                self.assertFalse(hook.is_blocked(cmd))


class TestFormats(unittest.TestCase):
    """
    Each agent receives the deny decision in its own output contract.
    """

    def test_claude_and_codex_use_hook_specific_output(self):
        """
        Claude Code and Codex share the PreToolUse permissionDecision shape.
        """
        for fmt in ["claude", "codex"]:
            with self.subTest(fmt=fmt):
                out, code = _run({"tool_input": {"command": "pyright"}}, fmt)
                self.assertEqual(code, 0)
                decision = json.loads(out)["hookSpecificOutput"]
                self.assertEqual(decision["permissionDecision"], "deny")
                self.assertIn("pipenv run", decision["permissionDecisionReason"])

    def test_gemini_uses_decision_and_reason(self):
        """
        Gemini CLI expects a top-level decision with a reason.
        """
        out, code = _run({"tool_input": {"command": "ruff check ."}}, "gemini")
        self.assertEqual(code, 0)
        body = json.loads(out)
        self.assertEqual(body["decision"], "deny")
        self.assertIn("pipenv run", body["reason"])

    def test_cursor_reads_top_level_command_and_uses_permission(self):
        """
        Cursor sends the command at the top level and expects `permission`.
        """
        out, code = _run({"command": "pytest"}, "cursor")
        self.assertEqual(code, 0)
        body = json.loads(out)
        self.assertEqual(body["permission"], "deny")
        self.assertIn("pipenv run", body["agent_message"])

    def test_cursor_allows_explicitly(self):
        """
        Cursor gets an explicit allow so the command is not left pending.
        """
        out, _ = _run({"command": "npm test"}, "cursor")
        self.assertEqual(json.loads(out), {"permission": "allow"})

    def test_allowed_command_prints_nothing_for_other_agents(self):
        """
        An allowed command produces no output, which every other agent reads as allow.
        """
        out, code = _run({"tool_input": {"command": "pipenv run pyright"}}, "claude")
        self.assertEqual((out, code), ("", 0))

    def test_malformed_payload_fails_open(self):
        """
        A payload that is not JSON never blocks the agent.
        """
        out, code = _run("not json", "codex")
        self.assertEqual((out, code), ("", 0))


if __name__ == "__main__":
    unittest.main()
