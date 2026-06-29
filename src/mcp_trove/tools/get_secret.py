"""``trove_get_secret`` — decrypt and return a secret's fields on the fly.

Requires the private key to be present at the configured key path. The decrypted
values are returned to the caller and never written back to disk.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from mcp_trove.config import load_config
from mcp_trove.crypto import decrypt_with, read_secret_key
from mcp_trove.vault import relative, secret_paths, slugify


def _resolve(vault: Path, name: str, category: Optional[str]) -> Optional[Path]:
    """Find the ``.age`` payload for ``name`` (a slug or title), optionally scoped
    to ``category``. Returns the path or None if not found / ambiguous-first-hit."""
    slug = slugify(name)
    if category:
        age_path, _ = secret_paths(vault, category, slug)
        return age_path if age_path.exists() else None
    matches = list((vault / "secrets").rglob(f"{slug}.age"))
    return matches[0] if matches else None


def get_secret(name: str, category: Optional[str] = None) -> dict[str, Any]:
    """Decrypt a secret and return its fields.

    Args:
        name: The secret title or slug.
        category: Optional category to disambiguate.

    Returns:
        A dict with ``fields`` and ``notes`` on success, or an ``error`` key.
    """
    config = load_config()
    age_path = _resolve(config.vault_path, name, category)
    if age_path is None:
        return {"error": config.pack.msg("not_found", path=name)}

    try:
        secret_key = read_secret_key(config.key_path)
    except (FileNotFoundError, ValueError) as exc:
        return {"error": str(exc)}

    plaintext = decrypt_with(age_path.read_bytes(), secret_key)
    data = json.loads(plaintext.decode("utf-8"))
    return {
        "path": relative(config.vault_path, age_path),
        "fields": data.get("fields", {}),
        "notes": data.get("notes"),
    }
