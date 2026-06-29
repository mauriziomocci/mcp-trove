"""``trove_add_secret`` — write an encrypted secret plus a cleartext metadata sidecar.

The secret values are JSON-serialised and encrypted in memory with age; the
plaintext never touches disk. The sidecar holds only non-sensitive metadata, so
the index and search can describe the secret without ever decrypting it.
"""

from __future__ import annotations

import json
from typing import Any, Optional

from mcp_trove.config import load_config
from mcp_trove.crypto import encrypt_for
from mcp_trove.index import build_index
from mcp_trove.vault import (
    build_frontmatter,
    parse_frontmatter,
    secret_paths,
    slugify,
    today_iso,
    write_bytes,
    write_file,
)


def add_secret(
    category: str,
    title: str,
    fields: dict[str, str],
    tags: Optional[list[str]] = None,
    notes: Optional[str] = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Create or update an encrypted secret entry.

    Args:
        category: Category folder under ``secrets/`` (e.g. "aws", "smtp").
        title: Human-readable title; the slug is derived from it.
        fields: Key/value secret material (username, password, token, …).
        tags: Cross-cutting tags (non-sensitive; stored in cleartext metadata).
        notes: Free text stored INSIDE the encrypted payload (may be sensitive).
        overwrite: Allow replacing an existing entry (preserving its created date).

    Returns:
        A report dict with the encrypted payload path. Values are never returned.

    Raises:
        ValueError: If no recipients are configured (run trove_init first).
    """
    config = load_config()
    if not config.recipients:
        raise ValueError(
            "no recipients configured in trove.toml — run trove_init to set up the key first."
        )

    slug = slugify(title)
    age_path, meta_path = secret_paths(config.vault_path, category, slug)

    created = today_iso()
    if age_path.exists() or meta_path.exists():
        if not overwrite:
            return {
                "error": f"secret already exists: {age_path}. Pass overwrite=true to replace it.",
                "path": str(age_path),
            }
        if meta_path.exists():
            existing = parse_frontmatter(meta_path.read_text(encoding="utf-8"))
            created = existing.get("created", created)

    payload = json.dumps({"fields": fields, "notes": notes}, ensure_ascii=False).encode("utf-8")
    ciphertext = encrypt_for(payload, config.recipients)
    write_bytes(age_path, ciphertext)

    meta = {
        "title": title,
        "category": slugify(category),
        "tags": tags or [],
        "type": "secret",
        "created": created,
        "updated": today_iso(),
    }
    # The sidecar carries metadata only (never values), as a frontmatter block.
    write_file(meta_path, build_frontmatter(meta) + "\n")

    count = build_index(config.vault_path)
    return {
        "message": config.pack.msg("secret_added", path=str(age_path)),
        "path": str(age_path),
        "meta": str(meta_path),
        "indexed": count,
    }
