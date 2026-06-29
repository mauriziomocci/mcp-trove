"""Tests for the ``trove`` CLI over an isolated vault.

The CLI is a thin front-end over the tools, so these tests focus on the parts the
CLI owns: argument routing, output rendering, the ``--field``/``--clip`` paths,
exit codes, and the TROVE_PATH-missing message.
"""

import json

from mcp_trove import cli
from mcp_trove.config import _reset_config
from mcp_trove.tools.add_secret import add_secret
from mcp_trove.tools.add_snippet import add_snippet


def test_get_prints_fields(vault, capsys):
    add_secret(category="aws", title="Prod key", fields={"user": "root", "password": "hunter2"})
    code = cli.run(["get", "Prod key"])
    out = capsys.readouterr().out
    assert code == cli.EXIT_OK
    assert "user" in out and "root" in out
    assert "password" in out and "hunter2" in out


def test_get_field_prints_only_value(vault, capsys):
    add_secret(category="aws", title="Prod key", fields={"password": "hunter2"})
    code = cli.run(["get", "Prod key", "--field", "password"])
    captured = capsys.readouterr()
    assert code == cli.EXIT_OK
    assert captured.out.strip() == "hunter2"


def test_get_unknown_field_errors(vault, capsys):
    add_secret(category="aws", title="Prod key", fields={"password": "hunter2"})
    code = cli.run(["get", "Prod key", "--field", "nope"])
    err = capsys.readouterr().err
    assert code == cli.EXIT_ERROR
    assert "nope" in err


def test_get_not_found_errors(vault, capsys):
    code = cli.run(["get", "missing"])
    assert code == cli.EXIT_ERROR
    assert capsys.readouterr().err  # a message was printed


def test_get_missing_key_errors(vault, capsys, monkeypatch):
    add_secret(category="aws", title="Prod key", fields={"password": "hunter2"})
    # Remove the private key so decryption cannot proceed.
    import os

    key_path = os.environ["TROVE_KEY_PATH"]
    os.remove(key_path)
    code = cli.run(["get", "Prod key"])
    assert code == cli.EXIT_ERROR
    assert capsys.readouterr().err


def test_get_json(vault, capsys):
    add_secret(category="aws", title="Prod key", fields={"password": "hunter2"})
    code = cli.run(["get", "Prod key", "--json"])
    out = capsys.readouterr().out
    assert code == cli.EXIT_OK
    data = json.loads(out)
    assert data["fields"] == {"password": "hunter2"}


def test_get_field_clip_copies_value(vault, capsys, monkeypatch):
    add_secret(category="aws", title="Prod key", fields={"password": "hunter2"})
    copied = {}
    monkeypatch.setattr(cli, "_copy_to_clipboard", lambda text: copied.setdefault("v", text) or True)
    code = cli.run(["get", "Prod key", "--field", "password", "--clip"])
    captured = capsys.readouterr()
    assert code == cli.EXIT_OK
    assert copied["v"] == "hunter2"
    assert "hunter2" not in captured.out  # value stays off stdout
    assert "clipboard" in captured.err


def test_get_clip_no_clipboard_errors(vault, capsys, monkeypatch):
    add_secret(category="aws", title="Prod key", fields={"password": "hunter2"})
    monkeypatch.setattr(cli, "_copy_to_clipboard", lambda text: False)
    code = cli.run(["get", "Prod key", "--clip"])
    assert code == cli.EXIT_ERROR
    assert "clipboard" in capsys.readouterr().err


def test_list(vault, capsys):
    add_snippet(domain="d", title="one", body_markdown="x")
    add_secret(category="c", title="two", fields={"k": "v"})
    code = cli.run(["list"])
    out = capsys.readouterr().out
    assert code == cli.EXIT_OK
    assert "one" in out and "two" in out


def test_search_secret_metadata(vault, capsys):
    add_secret(category="aws", title="Deploy key", fields={"k": "v"}, tags=["prod"])
    code = cli.run(["search", "deploy", "--kind", "secret"])
    out = capsys.readouterr().out
    assert code == cli.EXIT_OK
    assert "Deploy key" in out


def test_trove_path_unset_exits_config(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("TROVE_PATH", raising=False)
    _reset_config()
    code = cli.run(["list"])
    assert code == cli.EXIT_CONFIG
    assert "TROVE_PATH" in capsys.readouterr().err
    _reset_config()
