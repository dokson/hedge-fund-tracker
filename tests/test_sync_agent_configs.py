"""
Tests for scripts.sync_agent_configs: one manifest in .agents/ rendered into
every coding agent's own configuration folder.
"""

import json
import tempfile
import tomllib
import unittest
from pathlib import Path

from scripts.sync_agent_configs import check, sync

_MANIFEST = {
    "instructions": "AGENTS.md",
    "hooks": [
        {
            "name": "enforce-pipenv",
            "event": "pre-shell",
            "script": ".agents/hooks/enforce_pipenv.py",
            "timeout_seconds": 5,
        }
    ],
    "codex": {"approval_policy": "on-request", "sandbox_mode": "workspace-write"},
    "claude": {"settings": {"permissions": {"allow": ["Bash(npm test:*)"]}}},
}


class SyncAgentConfigsTest(unittest.TestCase):
    """
    Render, drift detection and skill mirroring against a temporary repo.
    """

    def setUp(self):
        """
        Create a throwaway repo with a manifest and one shared skill.
        """
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / ".agents" / "skills" / "demo").mkdir(parents=True)
        (self.root / ".agents" / "skills" / "demo" / "SKILL.md").write_text(
            "---\nname: demo\ndescription: d\n---\nbody\n", encoding="utf-8"
        )
        (self.root / ".agents" / "agents.json").write_text(json.dumps(_MANIFEST), encoding="utf-8")

    def tearDown(self):
        """
        Remove the temporary repo.
        """
        self._tmp.cleanup()

    def _json(self, rel: str) -> dict:
        """
        Load a generated JSON file.
        """
        return json.loads((self.root / rel).read_text(encoding="utf-8"))

    def test_renders_every_agent_from_the_manifest(self):
        """
        Each agent gets its hook wired in its own schema, pointing at the shared script.
        """
        sync(self.root)

        claude = self._json(".claude/settings.json")
        claude_hook = claude["hooks"]["PreToolUse"][0]
        self.assertEqual(claude_hook["matcher"], "Bash|PowerShell")
        self.assertIn(".agents/hooks/enforce_pipenv.py", claude_hook["hooks"][0]["command"])
        self.assertIn("--format claude", claude_hook["hooks"][0]["command"])
        self.assertEqual(claude["permissions"], {"allow": ["Bash(npm test:*)"]})

        codex_hook = self._json(".codex/hooks.json")["hooks"]["PreToolUse"][0]
        self.assertEqual(codex_hook["matcher"], "^Bash$")
        self.assertIn("--format codex", codex_hook["hooks"][0]["command"])

        gemini = self._json(".gemini/settings.json")
        self.assertEqual(gemini["context"]["fileName"], ["AGENTS.md"])
        gemini_hook = gemini["hooks"]["BeforeTool"][0]
        self.assertEqual(gemini_hook["matcher"], "run_shell_command")
        self.assertEqual(gemini_hook["hooks"][0]["timeout"], 5000)

        cursor = self._json(".cursor/hooks.json")
        self.assertEqual(cursor["version"], 1)
        self.assertIn("--format cursor", cursor["hooks"]["beforeShellExecution"][0]["command"])

        codex_config = tomllib.loads((self.root / ".codex/config.toml").read_text(encoding="utf-8"))
        self.assertEqual(codex_config["sandbox_mode"], "workspace-write")

    def test_mirrors_skills_and_prunes_stale_ones(self):
        """
        Shared skills are copied to agents that don't read .agents/skills; removed ones disappear.
        """
        stale = self.root / ".claude" / "skills" / "old"
        stale.mkdir(parents=True)
        (stale / "SKILL.md").write_text("old", encoding="utf-8")

        sync(self.root)

        for mirror in (".claude/skills/demo/SKILL.md", ".github/skills/demo/SKILL.md"):
            self.assertTrue((self.root / mirror).is_file(), mirror)
        self.assertFalse(stale.exists())

    def test_check_reports_drift_only_after_a_hand_edit(self):
        """
        `check` is clean right after a sync and names the file once it is edited by hand.
        """
        sync(self.root)
        self.assertEqual(check(self.root), [])

        (self.root / ".cursor" / "hooks.json").write_text("{}", encoding="utf-8")
        (self.root / ".claude" / "skills" / "demo" / "SKILL.md").unlink()

        self.assertEqual(
            sorted(check(self.root)),
            [".claude/skills/demo/SKILL.md", ".cursor/hooks.json"],
        )


if __name__ == "__main__":
    unittest.main()
