"""Configuration for mcp-trove.

The vault root is provided by the ``TROVE_PATH`` environment variable (required,
mirroring how mcp-cronos uses ``CRONOS_DIARIO_PATH``). Everything else is read
from ``trove.toml`` in the vault root, with sane defaults.

trove.toml shape::

    [trove]
    lang = "en"                 # "en" | "it"
    recipients = ["age1..."]    # age public keys secrets are encrypted for
    key_path = "~/.config/trove/key"   # optional; private key location
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover - exercised only on 3.10
    try:
        import tomli as tomllib  # type: ignore[no-redef]
    except ImportError:
        tomllib = None  # type: ignore[assignment]

from mcp_trove.i18n import LanguagePack, get_language_pack

DEFAULT_KEY_PATH = Path.home() / ".config" / "trove" / "key"


def get_vault_path() -> Path:
    """Return the vault root from ``TROVE_PATH``.

    Raises:
        RuntimeError: If ``TROVE_PATH`` is not set.
    """
    path_str = os.environ.get("TROVE_PATH")
    if not path_str:
        raise RuntimeError(
            "Environment variable TROVE_PATH is not set. Point it at your trove "
            "vault directory, e.g. TROVE_PATH=/path/to/trove"
        )
    return Path(path_str).expanduser()


@dataclass
class TroveConfig:
    """Resolved vault configuration."""

    lang: str
    recipients: list[str]
    key_path: Path
    vault_path: Path
    pack: LanguagePack = field(repr=False)


_config: Optional[TroveConfig] = None


def _reset_config() -> None:
    """Clear the cached config singleton. For tests only."""
    global _config
    _config = None


def _parse_toml(path: Path) -> dict[str, Any]:
    """Parse a TOML file, returning an empty dict on any error."""
    if tomllib is None or not path.exists():
        return {}
    try:
        with open(path, "rb") as fh:
            return tomllib.load(fh)
    except Exception:  # noqa: BLE001 - fall back to defaults on any parse error
        return {}


def load_config() -> TroveConfig:
    """Load, merge and cache the vault configuration.

    Resolution: values in ``{TROVE_PATH}/trove.toml`` override defaults. The
    result is cached; call :func:`_reset_config` to force a reload (tests).
    """
    global _config
    if _config is not None:
        return _config

    vault_path = get_vault_path()
    raw = _parse_toml(vault_path / "trove.toml")
    section: dict[str, Any] = raw.get("trove", {})

    lang = section.get("lang", "en")
    recipients = section.get("recipients", [])
    if not isinstance(recipients, list):
        recipients = []

    key_path_str = section.get("key_path") or os.environ.get("TROVE_KEY_PATH")
    key_path = Path(key_path_str).expanduser() if key_path_str else DEFAULT_KEY_PATH

    _config = TroveConfig(
        lang=lang,
        recipients=[str(r) for r in recipients],
        key_path=key_path,
        vault_path=vault_path,
        pack=get_language_pack(lang),
    )
    return _config
