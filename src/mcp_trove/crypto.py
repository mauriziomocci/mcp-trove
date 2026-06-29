"""Encryption helpers for mcp-trove.

This module is a thin wrapper over the `pyrage` library (Python bindings for the
`age` encryption tool). It deliberately implements **no cryptography of its own**:
key generation, encryption and decryption are delegated to vetted code. The vault
uses age x25519 keypairs; secret payloads are stored ASCII-armored so they live
nicely in git (line-based diffs, no binary blobs).

Key model
---------
- A single x25519 keypair guards the vault.
- The public part (an ``age1...`` recipient) is committed in ``trove.toml``.
- The private part (an ``AGE-SECRET-KEY-...`` identity) lives OUTSIDE the repo,
  by default at ``~/.config/trove/key``. Without it, nothing decrypts — by design.
"""

from __future__ import annotations

from pathlib import Path

from pyrage import decrypt, encrypt, x25519


def generate_keypair() -> tuple[str, str]:
    """Generate a fresh x25519 keypair.

    Returns:
        A ``(secret, public)`` tuple where ``secret`` is an ``AGE-SECRET-KEY-...``
        string (keep private) and ``public`` is an ``age1...`` recipient string
        (safe to commit).
    """
    identity = x25519.Identity.generate()
    return str(identity), str(identity.to_public())


def encrypt_for(data: bytes, recipients: list[str]) -> bytes:
    """Encrypt ``data`` for one or more age recipients, ASCII-armored.

    Args:
        data: Plaintext bytes to encrypt.
        recipients: age public keys (``age1...``).

    Returns:
        Armored ciphertext bytes (a ``-----BEGIN AGE ENCRYPTED FILE-----`` block).

    Raises:
        ValueError: If no recipients are provided.
    """
    if not recipients:
        raise ValueError("at least one recipient is required to encrypt")
    parsed = [x25519.Recipient.from_str(r) for r in recipients]
    return encrypt(data, parsed, armored=True)


def decrypt_with(data: bytes, secret_key: str) -> bytes:
    """Decrypt armored or binary age ciphertext with a secret identity.

    Args:
        data: Ciphertext bytes (armored or binary; age auto-detects).
        secret_key: An ``AGE-SECRET-KEY-...`` identity string.

    Returns:
        The decrypted plaintext bytes.
    """
    identity = x25519.Identity.from_str(secret_key)
    return decrypt(data, [identity])


def public_from_secret(secret_key: str) -> str:
    """Derive the ``age1...`` recipient string from an ``AGE-SECRET-KEY-...`` identity."""
    return str(x25519.Identity.from_str(secret_key).to_public())


def read_secret_key(key_path: Path) -> str:
    """Read and return the secret identity string from ``key_path``.

    The file is expected to contain a single ``AGE-SECRET-KEY-...`` line
    (comment lines starting with ``#`` are ignored, matching the age key format).

    Raises:
        FileNotFoundError: If the key file does not exist.
        ValueError: If no secret key line is found in the file.
    """
    if not key_path.exists():
        raise FileNotFoundError(
            f"age key not found at {key_path}. Run trove_init or restore your key backup."
        )
    for line in key_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            return line
    raise ValueError(f"no AGE-SECRET-KEY line found in {key_path}")
