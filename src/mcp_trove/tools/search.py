"""``trove_search`` — full-text over snippets, metadata-only over secrets.

Secret payloads (``.age``) are never read here, so a search can never surface a
secret value — only its title, tags and category from the cleartext sidecar.
"""

from __future__ import annotations

from typing import Any, Optional

from mcp_trove.config import load_config
from mcp_trove.vault import parse_frontmatter, relative


def _matches_tags(entry_tags: list[str], wanted: Optional[list[str]]) -> bool:
    if not wanted:
        return True
    lowered = {t.lower() for t in entry_tags}
    return all(w.lower() in lowered for w in wanted)


def _context(text: str, needle: str) -> str:
    """Return a short one-line context around the first match of ``needle``."""
    idx = text.lower().find(needle.lower())
    if idx < 0:
        return ""
    start = max(0, idx - 40)
    end = min(len(text), idx + len(needle) + 40)
    return " ".join(text[start:end].split())


def search(
    query: str = "",
    tags: Optional[list[str]] = None,
    kind: str = "all",
) -> dict[str, Any]:
    """Search the vault.

    Args:
        query: Free text. Matched in snippet body+frontmatter and in secret
            metadata (title/tags/category only).
        tags: Restrict to entries carrying all of these tags.
        kind: "snippet", "secret" or "all".

    Returns:
        A dict with the list of matches.
    """
    config = load_config()
    vault = config.vault_path
    q = query.strip().lower()
    results: list[dict[str, Any]] = []

    if kind in ("snippet", "all"):
        root = vault / "snippets"
        if root.exists():
            for md in sorted(root.rglob("*.md")):
                text = md.read_text(encoding="utf-8")
                fm = parse_frontmatter(text)
                etags = fm.get("tags", []) if isinstance(fm.get("tags"), list) else []
                if not _matches_tags(etags, tags):
                    continue
                if q and q not in text.lower():
                    continue
                results.append(
                    {
                        "kind": "snippet",
                        "title": fm.get("title", md.stem),
                        "tags": etags,
                        "path": relative(vault, md),
                        "context": _context(text, query) if q else "",
                    }
                )

    if kind in ("secret", "all"):
        root = vault / "secrets"
        if root.exists():
            for meta in sorted(root.rglob("*.meta.yaml")):
                fm = parse_frontmatter(meta.read_text(encoding="utf-8"))
                etags = fm.get("tags", []) if isinstance(fm.get("tags"), list) else []
                if not _matches_tags(etags, tags):
                    continue
                haystack = " ".join(
                    [fm.get("title", ""), fm.get("category", ""), " ".join(etags)]
                ).lower()
                if q and q not in haystack:
                    continue
                payload = meta.with_name(meta.name.replace(".meta.yaml", ".age"))
                results.append(
                    {
                        "kind": "secret",
                        "title": fm.get("title", ""),
                        "category": fm.get("category", ""),
                        "tags": etags,
                        "path": relative(vault, payload),
                    }
                )

    return {"count": len(results), "results": results}
