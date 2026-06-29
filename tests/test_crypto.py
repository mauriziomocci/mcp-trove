"""Crypto wrapper tests: keygen, roundtrip, key file parsing."""

import pytest

from mcp_trove.crypto import (
    decrypt_with,
    encrypt_for,
    generate_keypair,
    public_from_secret,
    read_secret_key,
)


def test_keypair_shape():
    secret, public = generate_keypair()
    assert secret.startswith("AGE-SECRET-KEY-1")
    assert public.startswith("age1")
    assert public_from_secret(secret) == public


def test_encrypt_decrypt_roundtrip():
    secret, public = generate_keypair()
    ciphertext = encrypt_for(b"top secret", [public])
    assert ciphertext.startswith(b"-----BEGIN AGE ENCRYPTED FILE-----")
    assert decrypt_with(ciphertext, secret) == b"top secret"


def test_encrypt_requires_recipient():
    with pytest.raises(ValueError):
        encrypt_for(b"x", [])


def test_read_secret_key(tmp_path):
    secret, _ = generate_keypair()
    key_file = tmp_path / "key"
    key_file.write_text(f"# created by test\n{secret}\n", encoding="utf-8")
    assert read_secret_key(key_file) == secret


def test_read_secret_key_missing(tmp_path):
    with pytest.raises(FileNotFoundError):
        read_secret_key(tmp_path / "nope")
