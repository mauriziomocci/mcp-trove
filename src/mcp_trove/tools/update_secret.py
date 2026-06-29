"""``trove_update_secret`` — change an existing secret without re-supplying it whole.

Rotating one credential should not force the caller to re-enter every field. This
decrypts the existing payload in memory, applies a partial change (set/remove
fields, update notes or tags), then re-encrypts. As with ``add_secret``, the
plaintext is only ever in memory; the ``created`` date is preserved and
``updated`` is bumped.
"""

from __future__ import annotations

import json
from typing import Any, Optional

from mcp_trove.config import load_config
from mcp_trove.crypto import decrypt_with, encrypt_for, read_secret_key
from mcp_trove.index import build_index
from mcp_trove.vault import (
    build_frontmatter,
    parse_frontmatter,
    resolve_secret,
    today_iso,
    write_bytes,
    write_file,
)

# Sentinel so "notes not given" is distinguishable from "clear the notes" ("").
_UNSET = object()


def update_secret(
    name: str,
    category: Optional[str] = None,
    set_fields: Optional[dict[str, str]] = None,
    remove_fields: Optional[list[str]] = None,
    notes: Any = _UNSET,
    tags: Optional[list[str]] = None,
) -> dict[str, Any]:
    """Apply a partial update to an existing secret.

    Args:
        name: Title or slug of the secret.
        category: Category to disambiguate when the slug exists in more than one.
        set_fields: Fields to add or overwrite (merged into the existing fields).
        remove_fields: Field names to drop.
        notes: New notes. Omit to keep the current notes; pass "" to clear them.
        tags: Replacement tag list for the cleartext sidecar (omit to keep).

    Returns:
        A report dict with the payload path, or an ``error`` key. Decryption needs
        the private key; re-encryption needs recipients in ``trove.toml``.
    """
    config = load_config()
    if not config.recipients:
        raise ValueError(
            "no recipients configured in trove.toml — run trove_init to set up the key first."
        )

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

    meta_path = age_path.with_name(age_path.name.replace(".age", ".meta.yaml"))

    try:
        secret_key = read_secret_key(config.key_path)
    except (FileNotFoundError, ValueError) as exc:
        return {"error": str(exc)}

    data = json.loads(decrypt_with(age_path.read_bytes(), secret_key).decode("utf-8"))
    fields: dict[str, str] = dict(data.get("fields", {}))
    if set_fields:
        fields.update(set_fields)
    for key in remove_fields or []:
        fields.pop(key, None)
    new_notes = data.get("notes") if notes is _UNSET else notes

    payload = json.dumps({"fields": fields, "notes": new_notes}, ensure_ascii=False).encode("utf-8")
    write_bytes(age_path, encrypt_for(payload, config.recipients))

    # Refresh the cleartext sidecar: preserve created/title/category, bump updated,
    # and replace tags only when a new list was provided.
    existing_meta = parse_frontmatter(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
    meta = {
        "title": existing_meta.get("title", name),
        "category": existing_meta.get("category", age_path.parent.name),
        "tags": tags if tags is not None else existing_meta.get("tags", []),
        "type": "secret",
        "created": existing_meta.get("created", today_iso()),
        "updated": today_iso(),
    }
    write_file(meta_path, build_frontmatter(meta) + "\n")

    count = build_index(config.vault_path)
    return {
        "message": config.pack.msg("secret_updated", path=str(age_path)),
        "path": str(age_path),
        "meta": str(meta_path),
        "fields_changed": sorted(set(set_fields or {}) | set(remove_fields or [])),
        "indexed": count,
    }
