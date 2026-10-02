"""
Encryption envelope tests. No DB needed — pure roundtrip checks.
"""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from cryptography.fernet import Fernet, InvalidToken

from app.security import envelope


def _fresh_kek_env(extra: dict[str, str] | None = None) -> dict[str, str]:
    """
    Build a clean env with a fresh MASTER_KEY (no MASTER_KEY_PREV by default).
    """
    env = {"MASTER_KEY": Fernet.generate_key().decode()}
    if extra:
        env.update(extra)
    return env


class TestEncryptDecryptDEK(unittest.TestCase):
    """
    DEK envelope: KEK -> encrypt(DEK) -> decrypt(ciphertext) -> DEK.
    """

    def setUp(self) -> None:
        """
        Reset module-level cache so each test sees a fresh KEK.
        """
        envelope.reset_kek_cache()

    def test_roundtrip_returns_same_dek(self) -> None:
        """
        encrypt_dek then decrypt_dek must yield the original bytes.
        """
        with patch.dict(os.environ, _fresh_kek_env(), clear=False):
            envelope.reset_kek_cache()
            dek = envelope.generate_dek()
            wrapped = envelope.encrypt_dek(dek)
            self.assertEqual(envelope.decrypt_dek(wrapped.ciphertext, wrapped.kek_version), dek)

    def test_decrypt_with_prev_kek_after_rotation(self) -> None:
        """
        After rotating MASTER_KEY, an old DEK encrypted with the previous KEK
        must still decrypt as long as MASTER_KEY_PREV is set.
        """
        old_kek = Fernet.generate_key().decode()
        with patch.dict(os.environ, {"MASTER_KEY": old_kek}, clear=False):
            envelope.reset_kek_cache()
            dek = envelope.generate_dek()
            old_wrapped = envelope.encrypt_dek(dek)

        # Rotate: old key moves to PREV, new primary takes its place.
        new_kek = Fernet.generate_key().decode()
        with patch.dict(
            os.environ,
            {"MASTER_KEY": new_kek, "MASTER_KEY_PREV": old_kek},
            clear=False,
        ):
            envelope.reset_kek_cache()
            self.assertEqual(
                envelope.decrypt_dek(old_wrapped.ciphertext, old_wrapped.kek_version),
                dek,
            )

    def test_missing_master_key_raises_at_use(self) -> None:
        """
        EncryptionConfigError fires the first time anyone tries to encrypt,
        not at import time.
        """
        envelope.reset_kek_cache()
        with patch.dict(os.environ, {}, clear=True):
            envelope.reset_kek_cache()
            with self.assertRaises(envelope.EncryptionConfigError):
                envelope.encrypt_dek(envelope.generate_dek())

    def test_invalid_master_key_format_raises(self) -> None:
        """
        Garbage in MASTER_KEY surfaces immediately, not as a failed decrypt later.
        """
        envelope.reset_kek_cache()
        with patch.dict(os.environ, {"MASTER_KEY": "not-base64-32-bytes"}, clear=False):
            envelope.reset_kek_cache()
            with self.assertRaises(envelope.EncryptionConfigError):
                envelope.encrypt_dek(envelope.generate_dek())


class TestEncryptDecryptValue(unittest.TestCase):
    """
    Value layer: DEK -> encrypt(plaintext) -> decrypt(ciphertext) -> plaintext.
    """

    def test_roundtrip_returns_same_string(self) -> None:
        """
        encrypt_value then decrypt_value yields the original string, non-ASCII included.
        """
        dek = envelope.generate_dek()
        for plaintext in ("sk-test-very-secret-12345", "key-with-émoji-🔑-and-ümlaut"):
            with self.subTest(plaintext=plaintext):
                ciphertext = envelope.encrypt_value(plaintext, dek)
                self.assertEqual(envelope.decrypt_value(ciphertext, dek), plaintext)

    def test_another_users_dek_cannot_decrypt(self) -> None:
        """
        A value is bound to its own DEK, so one user's key cannot read another's.
        """
        ciphertext = envelope.encrypt_value("sk-test-shared", envelope.generate_dek())
        with self.assertRaises(InvalidToken):
            envelope.decrypt_value(ciphertext, envelope.generate_dek())


if __name__ == "__main__":
    unittest.main()
