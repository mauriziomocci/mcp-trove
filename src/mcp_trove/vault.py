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

import yaml

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


def build_frontmatter(meta: dict[str, Any]) -> str:
    """Serialise a metadata dict into a YAML frontmatter block.

    Delegates to a real YAML emitter (PyYAML) so arbitrary strings — values with
    colons, hashes, commas, unicode — round-trip safely instead of relying on a
    hand-rolled escaper. ``None``/empty values are skipped; key order is preserved.
    """
    filtered = {
        key: value
        for key, value in meta.items()
        if value is not None and value != "" and not (isinstance(value, (list, tuple)) and not value)
    }
    body = yaml.safe_dump(
        filtered,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
    ).strip()
    return f"---\n{body}\n---"


def parse_frontmatter(text: str) -> dict[str, Any]:
    """Parse a leading YAML frontmatter block into a dict.

    Uses a real YAML loader, so it reads anything :func:`build_frontmatter` emits
    plus legacy inline ``[a, b]`` lists from earlier vault files. Returns an empty
    dict when no frontmatter is present or the block fails to parse.
    """
    match = _FRONTMATTER.match(text)
    if not match:
        return {}
    try:
        data = yaml.safe_load(match.group(1))
    except yaml.YAMLError:
        return {}
    return data if isinstance(data, dict) else {}


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


def resolve_secret(
    vault: Path, name: str, category: Optional[str]
) -> tuple[Optional[Path], set[str]]:
    """Locate the ``.age`` payload for ``name`` (a slug or title).

    Returns a ``(path, categories)`` pair. ``path`` is the resolved payload, or
    ``None`` when nothing matched or the match is ambiguous. ``categories`` lists
    every category whose folder holds a payload with this slug — used by callers
    to report an ambiguity ("exists in aws and gcp; pass the category") instead of
    silently picking the first hit.
    """
    slug = slugify(name)
    if category:
        age_path, _ = secret_paths(vault, category, slug)
        return (age_path if age_path.exists() else None), set()
    matches = list((vault / "secrets").rglob(f"{slug}.age"))
    categories = {m.parent.name for m in matches}
    if len(matches) == 1:
        return matches[0], categories
    return None, categories


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
