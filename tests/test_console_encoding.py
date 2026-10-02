import subprocess
import sys
import unittest


class TestPackageReconfiguresConsoleEncoding(unittest.TestCase):
    """
    Verifies that importing the top-level packages forces stdout/stderr to
    UTF-8, so emoji-laden prints (``❌``/``✅``) don't crash on Windows
    consoles defaulting to cp1252.

    Runs in a subprocess with PYTHONIOENCODING and PYTHONUTF8 explicitly
    cleared so the test exercises the reconfigure path, not an ambient
    environment override.
    """

    def _run(self, code: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            encoding="utf-8",
            env={"PATH": ""},  # strip PYTHONIOENCODING / PYTHONUTF8 from inherited env
            check=False,
        )

    def test_app_import_switches_stdout_to_utf8(self):
        """
        After ``import app`` stdout is utf-8 and an emoji print succeeds on any locale.
        """
        result = self._run("import app, sys; print(sys.stdout.encoding); print('❌ ok')")
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        encoding, line = result.stdout.splitlines()
        self.assertEqual(encoding.strip().lower().replace("-", ""), "utf8")
        self.assertEqual(line, "❌ ok")

    def test_database_import_allows_emoji_print(self):
        """
        After ``import database`` an emoji print must succeed on any locale.
        """
        result = self._run("import database; print('✅ ok')")
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("✅ ok", result.stdout)


if __name__ == "__main__":
    unittest.main()
