"""Vault primitives for mcp-trove: slugs, frontmatter, paths and file IO.

Layout managed here::

    <vault>/
      snippets/<domain>/<sub>/<slug>.md      plaintext markdown + frontmatter
      secrets/<category>/<slug>.age           encrypted payload (armored age)
      secrets/<category>/<slug>.meta.yaml     cleartext metadata, NEVER values
      _assets/

Secrets are split in two files on purpose: the ``.age`` holds the encrypted
fields, the ``.meta.yaml`` holds only non-sensitive metadata (title, tags, dates)
so that listing and search work without ever decrypting — the index can never
leak a secret value.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import date
from pathlib import Path
from typing import Any, Optional

_SLUG_STRIP = re.compile(r"[^a-z0-9]+")
_FRONTMATTER = re.compile(r"^---\n(.*?)\n---", re.DOTALL)


def slugify(text: str) -> str:
    """Turn a title into a kebab-case ASCII slug.

    Accents are folded to ASCII, non-alphanumerics collapse to single hyphens,
    leading/trailing hyphens are trimmed. Empty input yields ``"untitled"``.
    """
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii").lower()
    slug = _SLUG_STRIP.sub("-", ascii_text).strip("-")
    return slug or "untitled"


def _yaml_scalar(value: Any) -> str:
    """Render a scalar for our minimal frontmatter writer."""
    s = str(value)
    if s == "" or any(c in s for c in ":#") or s != s.strip():
        return f'"{s}"'
    return s


def build_frontmatter(meta: dict[str, Any]) -> str:
    """Serialise a metadata dict into a YAML frontmatter block.

    Lists render inline (``[a, b]``); ``None``/empty values are skipped. Key
    order is preserved as given by the caller.
    """
    lines = ["---"]
    for key, value in meta.items():
        if value is None or value == "":
            continue
        if isinstance(value, (list, tuple)):
            if not value:
                continue
            inline = ", ".join(_yaml_scalar(v) for v in value)
            lines.append(f"{key}: [{inline}]")
        else:
            lines.append(f"{key}: {_yaml_scalar(value)}")
    lines.append("---")
    return "\n".join(lines)


def parse_frontmatter(text: str) -> dict[str, Any]:
    """Parse a leading YAML frontmatter block into a dict.

    Handles the subset this project emits: scalars and inline ``[a, b]`` lists.
    Returns an empty dict when no frontmatter is present.
    """
    match = _FRONTMATTER.match(text)
    if not match:
        return {}
    data: dict[str, Any] = {}
    for line in match.group(1).splitlines():
        if ":" not in line:
            continue
        key, _, val = line.partition(":")
        key = key.strip()
        val = val.strip()
        if val.startswith("[") and val.endswith("]"):
            items = [v.strip().strip('"') for v in val[1:-1].split(",")]
            data[key] = [v for v in items if v]
        else:
            data[key] = val.strip('"')
    return data


def today_iso() -> str:
    """Return today's date as an ISO ``YYYY-MM-DD`` string."""
    return date.today().isoformat()


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------


def snippet_path(vault: Path, domain: str, subpath: Optional[str], slug: str) -> Path:
    """Resolve the markdown file path for a snippet."""
    parts = [vault, "snippets", slugify(domain)]
    if subpath:
        parts.extend(slugify(p) for p in subpath.split("/") if p)
    return Path(*parts) / f"{slug}.md"


def secret_paths(vault: Path, category: str, slug: str) -> tuple[Path, Path]:
    """Resolve the ``(payload.age, meta.yaml)`` pair for a secret."""
    base = Path(vault, "secrets", slugify(category))
    return base / f"{slug}.age", base / f"{slug}.meta.yaml"


# ---------------------------------------------------------------------------
# File IO
# ---------------------------------------------------------------------------


def write_file(path: Path, content: str) -> None:
    """Write text to ``path`` (UTF-8), creating parent directories."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def write_bytes(path: Path, content: bytes) -> None:
    """Write bytes to ``path``, creating parent directories."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def relative(vault: Path, path: Path) -> str:
    """Return ``path`` relative to the vault as a POSIX string (for reports)."""
    try:
        return path.relative_to(vault).as_posix()
    except ValueError:
        return path.as_posix()
