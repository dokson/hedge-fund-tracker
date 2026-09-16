"""
Tests for scripts.generate_secrets placeholder handling.
"""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from scripts.generate_secrets import _fresh_pairs, _replace_placeholder_values


class TestReplacePlaceholderValues(unittest.TestCase):
    """
    Verify that values copied verbatim from .env.example are regenerated.
    """

    def setUp(self):
        """
        Create a throwaway directory holding the env file under test.
        """
        self._tmp = TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.path = Path(self._tmp.name) / ".env"
        self.pairs = _fresh_pairs()

    def _write(self, text: str) -> None:
        """
        Write the given dotenv body to the env file under test.
        """
        self.path.write_text(text, encoding="utf-8")

    def test_replaces_example_placeholders_for_runtime_secrets(self):
        """
        MASTER_KEY and the token secrets left at their example values are
        replaced with freshly generated ones.
        """
        self._write(
            'MASTER_KEY="REPLACE_ME_with_a_freshly_generated_Fernet_key"\n'
            'RESET_PASSWORD_TOKEN_SECRET="REPLACE_ME_with_a_random_32_byte_secret"\n'
            "VERIFICATION_TOKEN_SECRET=your_secret_here\n"
        )

        replaced = _replace_placeholder_values(self.path, self.pairs)

        self.assertEqual(
            sorted(replaced),
            ["MASTER_KEY", "RESET_PASSWORD_TOKEN_SECRET", "VERIFICATION_TOKEN_SECRET"],
        )
        self.assertNotIn("REPLACE_ME", self.path.read_text(encoding="utf-8"))
        self.assertNotIn("your_secret_here", self.path.read_text(encoding="utf-8"))

    def test_leaves_postgres_password_untouched(self):
        """
        Rotating POSTGRES_PASSWORD after the database volume is initialized
        desynchronizes the app and the DB, so it is never repaired.
        """
        self._write('POSTGRES_PASSWORD="REPLACE_ME_with_a_strong_random_password"\n')

        replaced = _replace_placeholder_values(self.path, self.pairs)

        self.assertEqual(replaced, [])
        self.assertIn("REPLACE_ME_with_a_strong", self.path.read_text(encoding="utf-8"))

    def test_preserves_real_values_comments_and_blank_lines(self):
        """
        Only placeholder values change; everything else round-trips intact.
        """
        original = (
            "# comment\n"
            "\n"
            "MASTER_KEY=a-real-looking-key\n"
            "# MASTER_KEY=REPLACE_ME_commented_out\n"
            "GOOGLE_API_KEY=abc123\n"
        )
        self._write(original)

        replaced = _replace_placeholder_values(self.path, self.pairs)

        self.assertEqual(replaced, [])
        self.assertEqual(self.path.read_text(encoding="utf-8"), original)

    def test_returns_empty_when_file_is_missing(self):
        """
        A non-existent env file is not an error; there is nothing to repair.
        """
        self.assertEqual(_replace_placeholder_values(self.path, self.pairs), [])

    def test_keeps_values_containing_equals_signs(self):
        """
        Splitting on the first '=' must not truncate base64 padding.
        """
        self._write("MASTER_KEY=abc==\nVERIFICATION_TOKEN_SECRET=REPLACE_ME_x\n")

        _replace_placeholder_values(self.path, self.pairs)

        self.assertIn("MASTER_KEY=abc==", self.path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
