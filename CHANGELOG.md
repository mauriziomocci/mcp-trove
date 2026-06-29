# Changelog

All notable changes to mcp-trove are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0] - 2026-06-29

### Added

- `trove_update_secret` tool: partially update an existing secret (set/remove
  fields, change notes or tags) and re-encrypt, without re-supplying the whole
  payload. Preserves the `created` date; decryption needs the private key,
  re-encryption needs recipients.
- `trove` CLI bundled with the package (`[project.scripts]`): read and browse the
  vault from a terminal without a running MCP client and without an external
  `age` binary (decryption via the bundled `pyrage`). Subcommands `get`
  (`--field`, `--clip`, `--json`), `list`, `search` (`--tags`, `--kind`). `--clip`
  copies to the system clipboard (`pbcopy`/`wl-copy`/`xclip`/`xsel`/`clip`),
  keeping the value off the terminal. Reuses the existing `get_secret`,
  `list_entries` and `search` functions — no new crypto. Exit codes: 0 ok,
  1 application error, 2 if `TROVE_PATH` is unset.

### Changed

- Frontmatter is now read and written through PyYAML instead of a hand-rolled
  parser, so values with colons, hashes, commas or unicode round-trip safely.
  Backward compatible: legacy inline `[a, b]` lists still parse. Adds a `pyyaml`
  dependency.
- `trove_init` auto-enables the pre-commit hook (`git config core.hooksPath
  .githooks`) when the vault is a git repo, instead of only printing a hint; if a
  different hooks path is already set it is left untouched with a warning.
- `trove_doctor` adds a `git_remote_present` reminder (cleartext metadata gets
  pushed; keep the remote private) and no longer flags OS noise (`.DS_Store`,
  `Thumbs.db`) under `secrets/` as a cleartext-secret critical.

### Fixed

- `trove_get_secret` (and the `trove get` CLI) no longer silently return the
  first match when a slug exists in multiple categories: it now errors and lists
  the candidate categories so the caller can disambiguate.

### Documentation

- README: add a "Key management" section (EN + IT) covering key lookup order
  (`TROVE_KEY_PATH` / `trove.toml` `key_path` / default `~/.config/trove/key`),
  file format, backup, and step-by-step restore on another machine.
- README: add a "Reading secrets without the MCP" section (EN + IT) — leads with
  the `trove` CLI, with the `age`/`rage` CLI as a low-level fallback, and explains
  why the `secrets/` folder looks empty in Markdown readers (Obsidian lists only
  `.md`, not `.age`/`.meta.yaml`).

## [0.1.0] - 2026-06-29

### Added

- Initial release. MCP server managing a git-backed vault of plaintext snippets
  and encrypted secrets, with i18n (English default, Italian shipped).
- Encryption via `age` (through the `pyrage` binding); secrets are stored
  ASCII-armored so they live well in git. The private key lives outside the repo;
  the public recipient is committed in `trove.toml`.
- Tools: `trove_init`, `trove_add_snippet`, `trove_add_secret`,
  `trove_get_secret`, `trove_search`, `trove_list`, `trove_index`,
  `trove_remove`, `trove_doctor`.
- Secrets are split into an encrypted payload (`.age`) and a cleartext metadata
  sidecar (`.meta.yaml`) holding only non-sensitive fields, so the index and
  search never expose a secret value.
- `trove_doctor` read-only audit: missing key, no recipients, cleartext under
  `secrets/`, orphan payload/metadata, broken frontmatter, a private key in the
  tree, missing pre-commit hook.
