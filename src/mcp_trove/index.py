"""INDEX.md generation for mcp-trove.

Scans ``snippets/`` (markdown frontmatter) and ``secrets/`` (cleartext
``.meta.yaml`` sidecars), and writes an ``INDEX.md`` grouped by folder plus a tag
index. Secret values are never read here — only their metadata sidecars — so the
index cannot leak a secret.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from mcp_trove.vault import parse_frontmatter, relative


def _collect(vault: Path) -> list[dict[str, Any]]:
    """Gather index entries from snippets and secret metadata sidecars."""
    entries: list[dict[str, Any]] = []

    snippets_root = vault / "snippets"
    if snippets_root.exists():
        for md in sorted(snippets_root.rglob("*.md")):
            fm = parse_frontmatter(md.read_text(encoding="utf-8"))
            tags = fm.get("tags", [])
            entries.append(
                {
                    "kind": "snippet",
                    "title": fm.get("title", md.stem),
                    "tags": tags if isinstance(tags, list) else [],
                    "path": relative(vault, md),
                    "group": relative(vault, md.parent),
                }
            )

    secrets_root = vault / "secrets"
    if secrets_root.exists():
        for meta in sorted(secrets_root.rglob("*.meta.yaml")):
            fm = parse_frontmatter(meta.read_text(encoding="utf-8"))
            tags = fm.get("tags", [])
            # the encrypted payload sits next to the sidecar
            payload = meta.with_name(meta.name.replace(".meta.yaml", ".age"))
            entries.append(
                {
                    "kind": "secret",
                    "title": fm.get("title", meta.name.replace(".meta.yaml", "")),
                    "tags": tags if isinstance(tags, list) else [],
                    "path": relative(vault, payload),
                    "group": relative(vault, meta.parent),
                }
            )
    return entries


def build_index(vault: Path) -> int:
    """Regenerate ``<vault>/INDEX.md``. Returns the number of entries indexed."""
    entries = _collect(vault)

    lines = ["# Trove index", "", f"{len(entries)} entries.", ""]

    groups: dict[str, list[dict[str, Any]]] = {}
    for entry in entries:
        groups.setdefault(entry["group"], []).append(entry)

    for group in sorted(groups):
        lines.append(f"## {group}")
        lines.append("")
        for entry in sorted(groups[group], key=lambda x: x["title"].lower()):
            marker = "secret" if entry["kind"] == "secret" else "snippet"
            tags = " ".join(f"`{t}`" for t in entry["tags"])
            lines.append(f"- ({marker}) [{entry['title']}]({entry['path']}) {tags}".rstrip())
        lines.append("")

    tagmap: dict[str, list[dict[str, Any]]] = {}
    for entry in entries:
        for tag in entry["tags"]:
            tagmap.setdefault(tag, []).append(entry)

    if tagmap:
        lines.append("## Tags")
        lines.append("")
        for tag in sorted(tagmap):
            titles = ", ".join(
                f"[{e['title']}]({e['path']})"
                for e in sorted(tagmap[tag], key=lambda x: x["title"].lower())
            )
            lines.append(f"- **{tag}** ({len(tagmap[tag])}): {titles}")
        lines.append("")

    (vault / "INDEX.md").write_text("\n".join(lines), encoding="utf-8")
    return len(entries)
