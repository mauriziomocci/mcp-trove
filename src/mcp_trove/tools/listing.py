"""``trove_list`` and ``trove_index`` — read and regenerate the vault index."""

from __future__ import annotations

from typing import Any

from mcp_trove.config import load_config
from mcp_trove.index import _collect, build_index


def list_entries() -> dict[str, Any]:
    """Return the structured list of all entries (snippets and secrets)."""
    config = load_config()
    entries = _collect(config.vault_path)
    return {"count": len(entries), "entries": entries}


def rebuild_index() -> dict[str, Any]:
    """Regenerate ``INDEX.md`` from current frontmatter/metadata."""
    config = load_config()
    count = build_index(config.vault_path)
    return {"message": config.pack.msg("index_built", count=count), "indexed": count}
