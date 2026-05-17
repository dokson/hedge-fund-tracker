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

    def test_app_import_allows_emoji_print(self):
        """
        After ``import app`` an emoji print must succeed on any locale.
        """
        result = self._run("import app; print('❌ ok')")
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("❌ ok", result.stdout)

    def test_database_import_allows_emoji_print(self):
        """
        After ``import database`` an emoji print must succeed on any locale.
        """
        result = self._run("import database; print('✅ ok')")
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("✅ ok", result.stdout)

    def test_stdout_encoding_is_utf8_after_app_import(self):
        """
        ``sys.stdout.encoding`` must be utf-8 (case-insensitive) after import.
        """
        result = self._run("import app, sys; print(sys.stdout.encoding)")
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertEqual(result.stdout.strip().lower().replace("-", ""), "utf8")


if __name__ == "__main__":
    unittest.main()
