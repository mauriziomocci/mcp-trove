"""Internationalisation for mcp-trove.

A small frozen LanguagePack bundles the user-facing strings the server emits
(scaffolding messages, doctor findings, the CONVENTIONS document). English is the
default; Italian is shipped too. Tool names and schemas stay English regardless
of language — only human-readable messages are localised.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LanguagePack:
    """Locale-specific strings for a single language."""

    code: str
    messages: dict[str, str]

    def msg(self, key: str, **kwargs: object) -> str:
        """Return the localised message for ``key``, formatted with ``kwargs``.

        Falls back to the key itself if the message is missing, so a missing
        translation degrades to something readable instead of raising.
        """
        template = self.messages.get(key, key)
        try:
            return template.format(**kwargs)
        except (KeyError, IndexError):
            return template


_EN = LanguagePack(
    code="en",
    messages={
        "vault_initialized": "Trove initialized at {path}",
        "keypair_generated": "New age keypair generated. PUBLIC key committed to trove.toml.",
        "key_backup_warning": (
            "IMPORTANT: back up your private key ({key_path}) somewhere off this "
            "machine (e.g. your password manager). Without it the encrypted secrets "
            "are unrecoverable, even for you."
        ),
        "snippet_added": "Snippet saved: {path}",
        "secret_added": "Secret saved (encrypted): {path}",
        "removed": "Removed: {path}",
        "not_found": "Not found: {path}",
        "index_built": "INDEX.md rebuilt: {count} entries.",
        "doctor_clean": "No issues found.",
        "doctor_summary": "{count} issue(s) found.",
    },
)

_IT = LanguagePack(
    code="it",
    messages={
        "vault_initialized": "Trove inizializzato in {path}",
        "keypair_generated": "Nuova coppia di chiavi age generata. Chiave PUBBLICA salvata in trove.toml.",
        "key_backup_warning": (
            "IMPORTANTE: fai un backup della chiave privata ({key_path}) fuori da "
            "questa macchina (es. nel tuo password manager). Senza, i segreti cifrati "
            "sono irrecuperabili, anche per te."
        ),
        "snippet_added": "Snippet salvato: {path}",
        "secret_added": "Segreto salvato (cifrato): {path}",
        "removed": "Rimosso: {path}",
        "not_found": "Non trovato: {path}",
        "index_built": "INDEX.md rigenerato: {count} voci.",
        "doctor_clean": "Nessun problema rilevato.",
        "doctor_summary": "{count} problema/i rilevato/i.",
    },
)

_PACKS = {"en": _EN, "it": _IT}


def get_language_pack(lang: str) -> LanguagePack:
    """Return the LanguagePack for ``lang``, defaulting to English."""
    return _PACKS.get(lang, _EN)
