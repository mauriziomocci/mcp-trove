"""``trove_remove`` — delete an entry and regenerate the index.

For secrets, both the encrypted payload and its metadata sidecar are removed.
"""

from __future__ import annotations

from typing import Any, Optional

from mcp_trove.config import load_config
from mcp_trove.index import build_index
from mcp_trove.vault import relative, secret_paths, slugify, snippet_path


def remove_entry(
    name: str,
    kind: str,
    domain: Optional[str] = None,
    subpath: Optional[str] = None,
    category: Optional[str] = None,
) -> dict[str, Any]:
    """Remove a snippet or secret by name.

    Args:
        name: Title or slug of the entry.
        kind: "snippet" or "secret".
        domain, subpath: Location for a snippet.
        category: Category for a secret (recommended to disambiguate).

    Returns:
        A report dict listing the removed files, or an error.
    """
    config = load_config()
    vault = config.vault_path
    slug = slugify(name)
    removed: list[str] = []

    if kind == "snippet":
        if domain:
            candidates = [snippet_path(vault, domain, subpath, slug)]
        else:
            candidates = list((vault / "snippets").rglob(f"{slug}.md"))
        targets = [p for p in candidates if p.exists()]
    elif kind == "secret":
        if category:
            age_path, meta_path = secret_paths(vault, category, slug)
            targets = [p for p in (age_path, meta_path) if p.exists()]
        else:
            targets = []
            for age in (vault / "secrets").rglob(f"{slug}.age"):
                targets.append(age)
                meta = age.with_name(age.name.replace(".age", ".meta.yaml"))
                if meta.exists():
                    targets.append(meta)
    else:
        return {"error": f"unknown kind: {kind!r} (expected 'snippet' or 'secret')"}

    if not targets:
        return {"error": config.pack.msg("not_found", path=name)}

    for path in targets:
        path.unlink()
        removed.append(relative(vault, path))

    count = build_index(vault)
    return {
        "message": config.pack.msg("removed", path=", ".join(removed)),
        "removed": removed,
        "indexed": count,
    }
