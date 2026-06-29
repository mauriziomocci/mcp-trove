"""Unit tests for vault primitives: slug and frontmatter."""

from mcp_trove.vault import build_frontmatter, parse_frontmatter, slugify


def test_slugify_accents_and_spaces():
    assert slugify("Filtro tra due date") == "filtro-tra-due-date"
    assert slugify("Verifica se un punto è in un'area") == "verifica-se-un-punto-e-in-un-area"
    assert slugify("   ") == "untitled"


def test_frontmatter_roundtrip():
    meta = {"title": "X", "tags": ["a", "b"], "lang": "python", "empty": None}
    block = build_frontmatter(meta)
    parsed = parse_frontmatter(block + "\n\nbody")
    assert parsed["title"] == "X"
    assert parsed["tags"] == ["a", "b"]
    assert parsed["lang"] == "python"
    assert "empty" not in parsed


def test_parse_frontmatter_absent():
    assert parse_frontmatter("no frontmatter here") == {}


def test_frontmatter_handles_tricky_values():
    # Colons, hashes and commas inside a value must survive the round-trip.
    meta = {"title": "DB: host #1, port 5432", "tags": ["a, b", "c#d"]}
    parsed = parse_frontmatter(build_frontmatter(meta) + "\n\nbody")
    assert parsed["title"] == "DB: host #1, port 5432"
    assert parsed["tags"] == ["a, b", "c#d"]


def test_parse_frontmatter_legacy_inline_list():
    # Files written by the previous hand-rolled emitter used flow-style lists.
    legacy = "---\ntitle: X\ntags: [a, b]\n---\n\nbody"
    parsed = parse_frontmatter(legacy)
    assert parsed["title"] == "X"
    assert parsed["tags"] == ["a", "b"]
