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
