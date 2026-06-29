"""Shared fixtures: an initialized, isolated trove vault per test."""

import pytest

from mcp_trove.config import _reset_config
from mcp_trove.tools.init_vault import init_vault


@pytest.fixture
def vault(tmp_path, monkeypatch):
    """Provide a fresh, initialized vault with its key, isolated under tmp_path.

    Yields the vault Path. Config cache is reset before and after so each test
    sees its own TROVE_PATH.
    """
    vault_dir = tmp_path / "vault"
    key_path = tmp_path / "keydir" / "key"
    monkeypatch.setenv("TROVE_PATH", str(vault_dir))
    monkeypatch.setenv("TROVE_KEY_PATH", str(key_path))
    _reset_config()
    init_vault(lang="en")
    _reset_config()
    yield vault_dir
    _reset_config()
