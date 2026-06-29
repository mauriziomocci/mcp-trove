"""``trove`` — command-line reader for the vault, bundled with the MCP server.

This is a thin front-end over the same functions the MCP tools use
(:func:`get_secret`, :func:`list_entries`, :func:`search`). It lets anyone who
has the private key read and browse the vault straight from a terminal — no MCP
client running, and no external ``age`` binary, since decryption goes through the
``pyrage`` dependency already in use.

Security: the private key is the only secret and is never printed. ``get`` prints
secret values to stdout by design (same contract as ``trove_get_secret``); use
``--clip`` to copy a value to the clipboard instead, keeping it off the terminal
scrollback. ``search`` never reads the encrypted payloads.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from typing import Any, Optional

from mcp_trove.config import load_config
from mcp_trove.tools.get_secret import get_secret
from mcp_trove.tools.listing import list_entries
from mcp_trove.tools.search import search

# Exit codes: 0 ok, 1 application error, 2 misconfiguration (TROVE_PATH unset).
EXIT_OK = 0
EXIT_ERROR = 1
EXIT_CONFIG = 2


def _eprint(message: str) -> None:
    """Print to stderr (diagnostics and confirmations, never secret values)."""
    print(message, file=sys.stderr)


def _copy_to_clipboard(text: str) -> bool:
    """Copy ``text`` to the system clipboard via the platform command.

    Tries, in order, the clipboard tools commonly available per platform. Returns
    True on success, False if no clipboard command is available or it failed. No
    extra Python dependency is pulled in — this shells out to system binaries.
    """
    candidates: list[list[str]] = []
    if sys.platform == "darwin":
        candidates.append(["pbcopy"])
    elif sys.platform == "win32":
        candidates.append(["clip"])
    else:  # Linux / BSD: Wayland first, then X11.
        candidates.append(["wl-copy"])
        candidates.append(["xclip", "-selection", "clipboard"])
        candidates.append(["xsel", "--clipboard", "--input"])

    for cmd in candidates:
        if shutil.which(cmd[0]) is None:
            continue
        try:
            subprocess.run(cmd, input=text.encode("utf-8"), check=True)
            return True
        except (subprocess.SubprocessError, OSError):
            continue
    return False


def _render_fields(fields: dict[str, Any], notes: Optional[str]) -> str:
    """Render fields as aligned ``key: value`` lines, with notes appended."""
    lines: list[str] = []
    width = max((len(k) for k in fields), default=0)
    for key, value in fields.items():
        lines.append(f"{key.ljust(width)} : {value}")
    if notes:
        lines.append("")
        lines.append(f"notes: {notes}")
    return "\n".join(lines)


def _cmd_get(args: argparse.Namespace) -> int:
    result = get_secret(name=args.name, category=args.category)
    if "error" in result:
        _eprint(result["error"])
        return EXIT_ERROR

    fields: dict[str, Any] = result.get("fields", {})
    notes = result.get("notes")

    if args.json:
        # Explicit machine-readable dump (values included by request).
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return EXIT_OK

    if args.field is not None:
        if args.field not in fields:
            _eprint(f"field '{args.field}' not found in secret '{args.name}'")
            return EXIT_ERROR
        value = str(fields[args.field])
        if args.clip:
            if not _copy_to_clipboard(value):
                _eprint("no clipboard command available (pbcopy/wl-copy/xclip/xsel/clip)")
                return EXIT_ERROR
            _eprint(f"copied field '{args.field}' to clipboard")
        else:
            print(value)
        return EXIT_OK

    rendered = _render_fields(fields, notes)
    if args.clip:
        if not _copy_to_clipboard(rendered):
            _eprint("no clipboard command available (pbcopy/wl-copy/xclip/xsel/clip)")
            return EXIT_ERROR
        _eprint(f"copied secret '{args.name}' to clipboard")
    else:
        print(rendered)
    return EXIT_OK


def _cmd_list(args: argparse.Namespace) -> int:
    result = list_entries()
    entries = result.get("entries", [])
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return EXIT_OK

    if not entries:
        _eprint("vault is empty")
        return EXIT_OK
    for entry in entries:
        tags = ",".join(entry.get("tags", []))
        kind = entry.get("kind", "")
        title = entry.get("title", "")
        path = entry.get("path", "")
        print(f"[{kind:7}] {title}  ({tags})  -> {path}")
    return EXIT_OK


def _cmd_search(args: argparse.Namespace) -> int:
    result = search(query=args.query or "", tags=args.tags, kind=args.kind)
    results = result.get("results", [])
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return EXIT_OK

    if not results:
        _eprint("no matches")
        return EXIT_OK
    for entry in results:
        kind = entry.get("kind", "")
        title = entry.get("title", "")
        path = entry.get("path", "")
        context = entry.get("context", "")
        suffix = f"  | {context}" if context else ""
        print(f"[{kind:7}] {title}  -> {path}{suffix}")
    return EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser for the ``trove`` command."""
    parser = argparse.ArgumentParser(
        prog="trove",
        description="Read and search your trove vault from the terminal.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_get = sub.add_parser("get", help="decrypt and show a secret")
    p_get.add_argument("name", help="secret title or slug")
    p_get.add_argument("--category", "-c", default=None, help="category to disambiguate")
    p_get.add_argument("--field", "-f", default=None, help="print only this field's raw value")
    p_get.add_argument(
        "--clip", action="store_true", help="copy to the clipboard instead of printing"
    )
    p_get.add_argument("--json", action="store_true", help="emit the raw result as JSON")
    p_get.set_defaults(func=_cmd_get)

    p_list = sub.add_parser("list", help="list all entries")
    p_list.add_argument("--json", action="store_true", help="emit the raw result as JSON")
    p_list.set_defaults(func=_cmd_list)

    p_search = sub.add_parser("search", help="search snippets (full-text) and secrets (metadata)")
    p_search.add_argument("query", nargs="?", default="", help="free-text query")
    p_search.add_argument("--tags", "-t", nargs="+", default=None, help="require all these tags")
    p_search.add_argument(
        "--kind", "-k", choices=["snippet", "secret", "all"], default="all", help="entry kind"
    )
    p_search.add_argument("--json", action="store_true", help="emit the raw result as JSON")
    p_search.set_defaults(func=_cmd_search)

    return parser


def run(argv: Optional[list[str]] = None) -> int:
    """Entry point for the ``trove`` console script.

    Returns a process exit code; ``main`` wires it into ``sys.exit``.
    """
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        # Surface a clear message if TROVE_PATH is not set, before touching tools.
        load_config()
    except RuntimeError as exc:
        _eprint(str(exc))
        return EXIT_CONFIG
    return int(args.func(args))


def main() -> None:
    """Console-script shim: run and translate the return code into an exit."""
    sys.exit(run())


if __name__ == "__main__":
    main()
