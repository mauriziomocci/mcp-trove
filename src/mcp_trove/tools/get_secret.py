"""``trove_get_secret`` — decrypt and return a secret's fields on the fly.

Requires the private key to be present at the configured key path. The decrypted
values are returned to the caller and never written back to disk.
"""

from __future__ import annotations

import json
from typing import Any, Optional

from mcp_trove.config import load_config
from mcp_trove.crypto import decrypt_with, read_secret_key
from mcp_trove.vault import relative, resolve_secret


def get_secret(name: str, category: Optional[str] = None) -> dict[str, Any]:
    """Decrypt a secret and return its fields.

    Args:
        name: The secret title or slug.
        category: Optional category to disambiguate.

    Returns:
        A dict with ``fields`` and ``notes`` on success, or an ``error`` key. When
        the name matches secrets in more than one category and none was given, the
        error lists the candidate categories instead of guessing.
    """
    config = load_config()
    age_path, candidates = resolve_secret(config.vault_path, name, category)
    if age_path is None:
        if len(candidates) > 1:
            cats = ", ".join(sorted(candidates))
            return {
                "error": (
                    f"'{name}' is ambiguous — it exists in categories: {cats}. "
                    "Re-run with the category to disambiguate."
                ),
                "candidates": sorted(candidates),
            }
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
