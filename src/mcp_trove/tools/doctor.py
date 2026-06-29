"""``trove_doctor`` — read-only health and safety audit of the vault.

Reports problems with a severity (``critical``, ``warning``, ``info``) and an
actionable suggestion. Never modifies anything; never decrypts.
"""

from __future__ import annotations

import subprocess
from typing import Any

from mcp_trove.config import load_config
from mcp_trove.vault import parse_frontmatter, relative

_SECRET_KEY_MARKER = "AGE-SECRET-KEY-1"
# OS-generated noise that may appear in any folder; it is git-ignored and is not a
# plaintext secret, so the cleartext check skips it instead of crying wolf.
_OS_NOISE = {".DS_Store", "Thumbs.db"}


def _git_remotes(vault) -> list[str]:
    """Return configured git remote URLs for the vault, or [] if none / not git.

    Best-effort and offline: it cannot tell a private remote from a public one, so
    callers use this only to *remind* the user, never to assert a leak."""
    try:
        res = subprocess.run(
            ["git", "-C", str(vault), "remote", "-v"],
            capture_output=True,
            text=True,
        )
        if res.returncode != 0:
            return []
        urls = {line.split()[1] for line in res.stdout.splitlines() if len(line.split()) >= 2}
        return sorted(urls)
    except (OSError, subprocess.SubprocessError):
        return []


def _finding(severity: str, kind: str, where: str, message: str, fix: str) -> dict[str, str]:
    return {"severity": severity, "check": kind, "where": where, "message": message, "fix": fix}


def doctor() -> dict[str, Any]:
    """Audit the vault and return a list of findings ordered by severity."""
    config = load_config()
    vault = config.vault_path
    findings: list[dict[str, str]] = []

    # Key presence and recipients.
    if not config.key_path.exists():
        findings.append(
            _finding(
                "critical", "missing_key", str(config.key_path),
                "private age key not found; secrets cannot be decrypted",
                "restore the key from your off-machine backup, or run trove_init",
            )
        )
    if not config.recipients:
        findings.append(
            _finding(
                "critical", "no_recipients", "trove.toml",
                "no recipients configured; new secrets cannot be encrypted",
                "run trove_init or add an age public key under [trove] recipients",
            )
        )

    # Secrets store: pairing and stray cleartext.
    secrets_root = vault / "secrets"
    if secrets_root.exists():
        for path in secrets_root.rglob("*"):
            if path.is_dir() or path.name in _OS_NOISE:
                continue
            name = path.name
            if name.endswith(".age"):
                meta = path.with_name(name.replace(".age", ".meta.yaml"))
                if not meta.exists():
                    findings.append(
                        _finding(
                            "warning", "orphan_secret", relative(vault, path),
                            "encrypted payload without a metadata sidecar",
                            "recreate the .meta.yaml or remove the payload",
                        )
                    )
            elif name.endswith(".meta.yaml"):
                payload = path.with_name(name.replace(".meta.yaml", ".age"))
                if not payload.exists():
                    findings.append(
                        _finding(
                            "warning", "orphan_meta", relative(vault, path),
                            "metadata sidecar without an encrypted payload",
                            "re-add the secret or remove the stray sidecar",
                        )
                    )
            else:
                findings.append(
                    _finding(
                        "critical", "cleartext_in_secrets", relative(vault, path),
                        "unexpected non-encrypted file under secrets/ (possible plaintext secret)",
                        "move it out, or store it via trove_add_secret so it gets encrypted",
                    )
                )

    # Snippet frontmatter sanity.
    snippets_root = vault / "snippets"
    if snippets_root.exists():
        for md in snippets_root.rglob("*.md"):
            fm = parse_frontmatter(md.read_text(encoding="utf-8"))
            if not fm.get("title"):
                findings.append(
                    _finding(
                        "warning", "broken_frontmatter", relative(vault, md),
                        "snippet has no title in frontmatter",
                        "add a title; re-save via trove_add_snippet with overwrite",
                    )
                )

    # A private key in cleartext anywhere in the tree.
    for path in vault.rglob("*"):
        if path.is_dir() or path == config.key_path:
            continue
        # Skip binary assets and the hooks dir (the pre-commit script legitimately
        # contains the marker string in its own grep pattern).
        if "_assets" in path.parts or ".githooks" in path.parts:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if _SECRET_KEY_MARKER in text:
            findings.append(
                _finding(
                    "critical", "private_key_in_tree", relative(vault, path),
                    "a private age key appears in cleartext inside the vault",
                    "remove it immediately and rotate the key; it must never be committed",
                )
            )

    # Git remote reminder: secret VALUES are encrypted, but the .meta.yaml sidecars
    # (titles, tags, categories) are cleartext and get pushed. If a remote exists,
    # remind the user it must be private and titles should not carry sensitive info.
    remotes = _git_remotes(vault)
    if remotes:
        findings.append(
            _finding(
                "info", "git_remote_present", ", ".join(remotes),
                "the vault has a git remote; secret metadata (titles, tags, categories) "
                "is stored in cleartext and will be pushed",
                "ensure the remote is private and keep sensitive details out of secret titles",
            )
        )

    # Pre-commit safety net present?
    if not (vault / ".githooks" / "pre-commit").exists():
        findings.append(
            _finding(
                "info", "no_precommit", ".githooks/pre-commit",
                "no pre-commit safety hook installed",
                "run trove_init, then: git config core.hooksPath .githooks",
            )
        )

    order = {"critical": 0, "warning": 1, "info": 2}
    findings.sort(key=lambda f: order.get(f["severity"], 9))

    if not findings:
        summary = config.pack.msg("doctor_clean")
    else:
        summary = config.pack.msg("doctor_summary", count=len(findings))

    counts = {
        sev: sum(1 for f in findings if f["severity"] == sev)
        for sev in ("critical", "warning", "info")
    }
    return {"summary": summary, "counts": counts, "findings": findings}
