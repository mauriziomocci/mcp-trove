"""``trove_add_snippet`` — write a plaintext snippet with frontmatter."""

from __future__ import annotations

from typing import Any, Optional

from mcp_trove.config import load_config
from mcp_trove.index import build_index
from mcp_trove.vault import (
    build_frontmatter,
    parse_frontmatter,
    slugify,
    snippet_path,
    today_iso,
    write_file,
)


def add_snippet(
    domain: str,
    title: str,
    body_markdown: str,
    tags: Optional[list[str]] = None,
    lang: str = "text",
    subpath: Optional[str] = None,
    project: Optional[str] = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Create or update a snippet markdown file.

    The model supplies ``body_markdown`` already segmented (prose outside fences,
    code inside fenced blocks with the right language). This tool only persists:
    it builds the frontmatter, places the file under ``snippets/<domain>/...`` and
    regenerates the index.

    Args:
        domain: Primary domain folder (e.g. "django").
        title: Human-readable title; the slug is derived from it.
        body_markdown: The note body, below the H1 title.
        tags: Cross-cutting tags.
        lang: Language of the main code block ("python", "html", "bash", "text"…).
        subpath: Optional sub-folder under the domain (e.g. "orm").
        project: Optional generic project name.
        overwrite: Allow replacing an existing file (preserving its created date).

    Returns:
        A report dict with the written path.
    """
    config = load_config()
    slug = slugify(title)
    path = snippet_path(config.vault_path, domain, subpath, slug)

    created = today_iso()
    if path.exists():
        if not overwrite:
            return {
                "error": f"snippet already exists: {path}. Pass overwrite=true to replace it.",
                "path": str(path),
            }
        existing = parse_frontmatter(path.read_text(encoding="utf-8"))
        created = existing.get("created", created)

    meta = {
        "title": title,
        "tags": tags or [],
        "lang": lang,
        "type": "snippet",
        "project": project,
        "created": created,
        "updated": today_iso(),
    }
    content = f"{build_frontmatter(meta)}\n\n# {title}\n\n{body_markdown.rstrip()}\n"
    write_file(path, content)

    count = build_index(config.vault_path)
    return {
        "message": config.pack.msg("snippet_added", path=str(path)),
        "path": str(path),
        "indexed": count,
    }
