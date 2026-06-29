"""``trove_init`` — scaffold a new vault.

Creates the directory layout, resolves or generates the age keypair, writes
``trove.toml``, a ``.gitignore``, a CONVENTIONS document and a defensive
pre-commit hook. Idempotent: existing files are left untouched.
"""

from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path
from typing import Any, Optional

from mcp_trove.config import DEFAULT_KEY_PATH, get_vault_path
from mcp_trove.crypto import generate_keypair, public_from_secret, read_secret_key
from mcp_trove.i18n import get_language_pack

_GITIGNORE = """\
# Never commit the private age key
key
*.key
*.agekey
# OS noise
.DS_Store
Thumbs.db
"""

_CONVENTIONS = """\
# Trove conventions

This vault is managed by mcp-trove. Two kinds of entry live here.

## Snippets (plaintext)

`snippets/<domain>/<sub>/<slug>.md`, each with YAML frontmatter:

```markdown
---
title: Human readable title
tags: [domain, concept]
lang: python
type: snippet
created: 2026-01-01
updated: 2026-01-01
---

Prose outside fenced blocks. Code inside fences with the right language.
```

Code is stored verbatim. Images go in `_assets/` and are referenced with
relative links. Logical diagrams use ```mermaid``` blocks.

## Secrets (encrypted)

Each secret is two files:

- `secrets/<category>/<slug>.age` — the encrypted payload (armored age).
- `secrets/<category>/<slug>.meta.yaml` — cleartext metadata only (title, tags,
  dates). It never contains secret values, so listing and search are safe.

The private key lives OUTSIDE this repo. Back it up off-machine: without it the
secrets are unrecoverable.

Caveat: the `.meta.yaml` sidecars are cleartext and get pushed with the vault.
Secret VALUES stay encrypted, but titles, tags and category names do not. Keep
the git remote PRIVATE and avoid putting sensitive details in secret titles
(prefer "Prod DB" over "Prod DB root password h***").
"""

def _enable_hook(vault: Path) -> tuple[bool, Optional[str]]:
    """Wire the pre-commit safety net into git when the vault is a git work tree.

    The hook is useless until ``core.hooksPath`` points at ``.githooks``; requiring
    the user to set it by hand means it is usually never enabled. So: if the vault
    is a git repo and ``core.hooksPath`` is unset, set it. If the user already set
    a different hooks path, leave it and return a warning rather than clobbering.

    Returns ``(enabled, warning)``. Any git/environment error degrades gracefully
    to ``(False, None)`` — enabling the hook is best-effort, never fatal to init.
    """
    try:
        inside = subprocess.run(
            ["git", "-C", str(vault), "rev-parse", "--is-inside-work-tree"],
            capture_output=True,
            text=True,
        )
        if inside.returncode != 0 or inside.stdout.strip() != "true":
            return False, None
        current = subprocess.run(
            ["git", "-C", str(vault), "config", "--local", "--get", "core.hooksPath"],
            capture_output=True,
            text=True,
        )
        existing = current.stdout.strip()
        if existing and existing != ".githooks":
            return False, (
                f"core.hooksPath is set to '{existing}', not '.githooks' — left as is. "
                "Point it at .githooks to enable the trove secret-blocking hook."
            )
        if existing == ".githooks":
            return True, None
        set_res = subprocess.run(
            ["git", "-C", str(vault), "config", "--local", "core.hooksPath", ".githooks"],
            capture_output=True,
            text=True,
        )
        return (set_res.returncode == 0), None
    except (OSError, subprocess.SubprocessError):
        return False, None


_PRECOMMIT = """\
#!/bin/sh
# Trove safety net: block commits that contain a private age key in cleartext.
# Enable with: git config core.hooksPath .githooks
if git diff --cached -U0 | grep -qE 'AGE-SECRET-KEY-1'; then
  echo "trove: refusing commit — an AGE-SECRET-KEY appears in the staged changes." >&2
  echo "Remove it; the private key must never be committed." >&2
  exit 1
fi
exit 0
"""


def init_vault(
    recipient: Optional[str] = None,
    lang: str = "en",
    generate_key: bool = True,
) -> dict[str, Any]:
    """Scaffold the vault rooted at ``TROVE_PATH``.

    Args:
        recipient: An explicit age public key to encrypt secrets for. If given,
            no keypair is generated (you manage the key yourself).
        lang: UI language for messages ("en" or "it").
        generate_key: When no recipient is given and no key exists yet, generate
            a fresh keypair and store the private part at the key path.

    Returns:
        A report dict with the created paths, the recipient, and warnings.
    """
    vault = get_vault_path()
    pack = get_language_pack(lang)
    key_path = Path(os.environ.get("TROVE_KEY_PATH", str(DEFAULT_KEY_PATH))).expanduser()

    created: list[str] = []
    warnings: list[str] = []

    for sub in ("snippets", "secrets", "_assets", ".githooks"):
        d = vault / sub
        if not d.exists():
            d.mkdir(parents=True, exist_ok=True)
            created.append(f"{sub}/")

    # Resolve the recipient.
    key_generated = False
    if recipient:
        resolved_recipient = recipient
    elif key_path.exists():
        resolved_recipient = public_from_secret(read_secret_key(key_path))
    elif generate_key:
        secret, resolved_recipient = generate_keypair()
        key_path.parent.mkdir(parents=True, exist_ok=True)
        key_path.write_text(secret + "\n", encoding="utf-8")
        os.chmod(key_path, stat.S_IRUSR | stat.S_IWUSR)  # 0600
        key_generated = True
        created.append(str(key_path))
    else:
        resolved_recipient = ""
        warnings.append("No recipient provided and key generation disabled: secrets cannot be encrypted yet.")

    # trove.toml (only if absent, to avoid clobbering user edits).
    toml_path = vault / "trove.toml"
    if not toml_path.exists():
        recipients_line = f'["{resolved_recipient}"]' if resolved_recipient else "[]"
        toml_path.write_text(
            f'[trove]\nlang = "{lang}"\nrecipients = {recipients_line}\n',
            encoding="utf-8",
        )
        created.append("trove.toml")

    for rel, content, mode in (
        (".gitignore", _GITIGNORE, None),
        ("CONVENTIONS.md", _CONVENTIONS, None),
        (".githooks/pre-commit", _PRECOMMIT, 0o755),
    ):
        p = vault / rel
        if not p.exists():
            p.write_text(content, encoding="utf-8")
            if mode is not None:
                os.chmod(p, mode)
            created.append(rel)

    if key_generated or key_path.exists():
        warnings.append(pack.msg("key_backup_warning", key_path=str(key_path)))

    # Best-effort: wire the pre-commit hook into git so the safety net is actually live.
    hooks_enabled, hook_warning = _enable_hook(vault)
    if hook_warning:
        warnings.append(hook_warning)
    next_step = (
        "Pre-commit secret-blocking hook is active (core.hooksPath = .githooks)."
        if hooks_enabled
        else "Enable the safety hook with: git config core.hooksPath .githooks"
    )

    return {
        "message": pack.msg("vault_initialized", path=str(vault)),
        "vault": str(vault),
        "recipient": resolved_recipient,
        "key_path": str(key_path),
        "key_generated": key_generated,
        "created": created,
        "hooks_enabled": hooks_enabled,
        "warnings": warnings,
        "next_step": next_step,
    }
