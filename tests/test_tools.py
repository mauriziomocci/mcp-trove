"""Integration tests for the trove tools over an isolated vault."""

from mcp_trove.tools.add_secret import add_secret
from mcp_trove.tools.add_snippet import add_snippet
from mcp_trove.tools.doctor import doctor
from mcp_trove.tools.get_secret import get_secret
from mcp_trove.tools.listing import list_entries, rebuild_index
from mcp_trove.tools.remove import remove_entry
from mcp_trove.tools.search import search


def test_init_creates_layout(vault):
    assert (vault / "snippets").is_dir()
    assert (vault / "secrets").is_dir()
    assert (vault / "trove.toml").exists()
    assert (vault / "CONVENTIONS.md").exists()
    assert (vault / ".githooks" / "pre-commit").exists()


def test_add_snippet_writes_and_indexes(vault):
    res = add_snippet(
        domain="Django",
        title="ORM N+1",
        body_markdown="Prose.\n\n```python\nx = 1\n```",
        tags=["django", "orm"],
        lang="python",
        subpath="orm",
    )
    path = vault / "snippets" / "django" / "orm" / "orm-n-1.md"
    assert path.exists()
    text = path.read_text(encoding="utf-8")
    assert "title: ORM N+1" in text
    assert "x = 1" in text  # code preserved verbatim
    assert res["indexed"] == 1


def test_add_snippet_no_overwrite(vault):
    add_snippet(domain="d", title="t", body_markdown="a")
    res = add_snippet(domain="d", title="t", body_markdown="b")
    assert "error" in res


def test_secret_roundtrip_and_index_has_no_value(vault):
    add_secret(
        category="AWS",
        title="Prod key",
        fields={"access_key": "AKIA123", "secret": "topsecret"},
        tags=["aws", "prod"],
        notes="rotate quarterly",
    )
    got = get_secret(name="Prod key", category="AWS")
    assert got["fields"] == {"access_key": "AKIA123", "secret": "topsecret"}
    assert got["notes"] == "rotate quarterly"

    # The cleartext index and metadata must not contain the secret value.
    index_text = (vault / "INDEX.md").read_text(encoding="utf-8")
    assert "topsecret" not in index_text
    meta_text = (vault / "secrets" / "aws" / "prod-key.meta.yaml").read_text(encoding="utf-8")
    assert "topsecret" not in meta_text
    assert "AKIA123" not in meta_text


def test_search_snippet_and_secret(vault):
    add_snippet(domain="django", title="Date filter", body_markdown="filter by created date")
    add_secret(category="aws", title="Deploy key", fields={"k": "v"}, tags=["prod"])

    snip = search(query="created", kind="snippet")
    assert snip["count"] == 1 and snip["results"][0]["title"] == "Date filter"

    sec = search(query="deploy", kind="secret")
    assert sec["count"] == 1 and sec["results"][0]["category"] == "aws"

    by_tag = search(tags=["prod"])
    assert by_tag["count"] == 1


def test_list_and_reindex(vault):
    add_snippet(domain="d", title="one", body_markdown="x")
    add_secret(category="c", title="two", fields={"k": "v"})
    listed = list_entries()
    assert listed["count"] == 2
    assert rebuild_index()["indexed"] == 2


def test_remove_secret_deletes_both_files(vault):
    add_secret(category="aws", title="Gone", fields={"k": "v"})
    age = vault / "secrets" / "aws" / "gone.age"
    meta = vault / "secrets" / "aws" / "gone.meta.yaml"
    assert age.exists() and meta.exists()
    remove_entry(name="Gone", kind="secret", category="aws")
    assert not age.exists() and not meta.exists()


def test_doctor_clean_then_detects_cleartext(vault):
    assert doctor()["counts"]["critical"] == 0
    # Drop a stray cleartext file under secrets/ -> must be flagged critical.
    (vault / "secrets" / "leak.txt").write_text("password=hunter2", encoding="utf-8")
    report = doctor()
    assert report["counts"]["critical"] >= 1
    assert any(f["check"] == "cleartext_in_secrets" for f in report["findings"])
