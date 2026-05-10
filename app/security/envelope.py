"""
Envelope encryption for BYOK API keys.

Two-layer scheme:

    master KEK (env var, NEVER in DB)
        ↓ encrypts
    per-user DEK (random, stored in user_secrets.dek_ciphertext)
        ↓ encrypts
    api_keys.encrypted_value

A DB dump alone is useless — it has DEK ciphertexts but no KEK to decrypt them.
The KEK lives only in the deployment environment (`MASTER_KEY` env var, Fly
secret / systemd EnvironmentFile / Hetzner private file).

Key rotation:
- **DEK rotation**: generate new DEK, re-encrypt that user's api_keys with it,
  update user_secrets.dek_ciphertext. ~1ms per key.
- **KEK rotation**: support two active versions via MASTER_KEY (current) and
  MASTER_KEY_PREV (decrypt-only). Each user_secrets row records which KEK
  version encrypted its DEK. Background job re-encrypts old DEKs to the new
  KEK, then drops the old version.

Library: `cryptography.fernet` (AES-128-CBC + HMAC-SHA256, IV per message,
authenticated). Keys are 32-byte url-safe base64. Sufficient for this use
case; if we ever need post-quantum or AEAD with associated data, swap to
nacl.secret.SecretBox.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Final

from cryptography.fernet import Fernet, InvalidToken, MultiFernet

logger = logging.getLogger(__name__)

# Env vars holding KEKs. MASTER_KEY is the current/write key; MASTER_KEY_PREV
# is the previous one (read-only) during a rotation window. Both must be
# 32-byte url-safe base64 strings (run `Fernet.generate_key()` to make one).
_MASTER_KEY_ENV: Final = "MASTER_KEY"
_MASTER_KEY_PREV_ENV: Final = "MASTER_KEY_PREV"

# Bumped on every KEK rotation. Stored on each user_secrets row so we know
# which KEK encrypted that DEK and can roll it forward later.
_CURRENT_KEK_VERSION: Final = int(os.environ.get("MASTER_KEY_VERSION", "1"))


class EncryptionConfigError(RuntimeError):
    """
    Raised at startup when the KEK environment isn't set correctly.
    Fail fast — running without a KEK would silently produce un-decryptable data.
    """


def _load_kek() -> Fernet | MultiFernet:
    """
    Build a Fernet (or MultiFernet, if MASTER_KEY_PREV is set) from env.
    Validates format eagerly so misconfiguration crashes startup rather than
    surfacing on the first signup.
    """
    primary = os.environ.get(_MASTER_KEY_ENV)
    if not primary:
        raise EncryptionConfigError(
            f"{_MASTER_KEY_ENV} env var is required. "
            f'Generate one with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"'
        )

    keys = [primary]
    prev = os.environ.get(_MASTER_KEY_PREV_ENV)
    if prev:
        keys.append(prev)

    try:
        fernets = [Fernet(k.encode()) for k in keys]
    except (ValueError, TypeError) as exc:
        raise EncryptionConfigError(
            f"Invalid KEK format. Both {_MASTER_KEY_ENV} and {_MASTER_KEY_PREV_ENV} "
            "(if set) must be url-safe base64 of 32 bytes."
        ) from exc

    return MultiFernet(fernets) if len(fernets) > 1 else fernets[0]


# Lazily initialized so importing this module doesn't crash in test environments
# that don't set MASTER_KEY. Call sites that actually encrypt/decrypt will trigger
# the load via _kek().
_KEK: Fernet | MultiFernet | None = None


def _kek() -> Fernet | MultiFernet:
    """
    Cached KEK accessor. First call validates env; subsequent calls return the
    cached instance.
    """
    global _KEK
    if _KEK is None:
        _KEK = _load_kek()
    return _KEK


def reset_kek_cache() -> None:
    """
    Drop the cached KEK so the next encrypt/decrypt re-reads env vars. Test
    helper — production code never calls this.
    """
    global _KEK
    _KEK = None


@dataclass(frozen=True)
class EncryptedDEK:
    """
    A user's data encryption key, ready to persist in `user_secrets`.
    """

    ciphertext: bytes
    kek_version: int


def generate_dek() -> bytes:
    """
    Generate a fresh DEK. 32 random bytes wrapped in Fernet's url-safe base64.
    """
    return Fernet.generate_key()


def encrypt_dek(plaintext_dek: bytes) -> EncryptedDEK:
    """
    Encrypt a DEK with the current KEK. Returned bundle is what we persist.
    """
    return EncryptedDEK(
        ciphertext=_kek().encrypt(plaintext_dek),
        kek_version=_CURRENT_KEK_VERSION,
    )


def decrypt_dek(ciphertext: bytes, kek_version: int) -> bytes:  # noqa: ARG001
    """
    Decrypt a DEK ciphertext. `kek_version` is currently informational — the
    MultiFernet under the hood transparently tries every available KEK. We
    keep the parameter so the caller's contract doesn't change when we add
    explicit version routing.
    """
    try:
        return _kek().decrypt(ciphertext)
    except InvalidToken as exc:
        raise EncryptionConfigError(
            f"Failed to decrypt DEK encrypted under KEK version {kek_version}. "
            "Has MASTER_KEY been rotated without setting MASTER_KEY_PREV?"
        ) from exc


def encrypt_value(plaintext: str, dek: bytes) -> bytes:
    """
    Encrypt a user-facing secret (e.g. an API key) with the user's DEK.
    """
    return Fernet(dek).encrypt(plaintext.encode("utf-8"))


def decrypt_value(ciphertext: bytes, dek: bytes) -> str:
    """
    Decrypt a value previously stored via `encrypt_value`.
    """
    return Fernet(dek).decrypt(ciphertext).decode("utf-8")
