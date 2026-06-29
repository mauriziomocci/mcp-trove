# mcp-trove — Specification

> Status: DRAFT for approval (phase-2 gate). Items marked **[default]** are
> proposed defaults, vetoable before implementation.

## 1. What it is

`mcp-trove` is a general-purpose MCP server that manages a **trove**: a
git-backed vault holding two kinds of entries.

- **Snippets** — code/notes in plaintext Markdown, searchable, with images,
  diagrams and links.
- **Secrets** — credentials/tokens stored **encrypted at rest**, so the vault
  can be pushed to a private remote (GitHub) without exposing them.

A trove holds both treasures (secrets) and finds (snippets) — hence the name.

The server is the **deterministic writer** over the vault. The calling model
composes and cleans content; the server guarantees placement, slug, frontmatter,
encryption and index — always the same, no drift.

Audience: international, published on PyPI. Tool names and shipped docs are in
English; user-facing messages are translatable via i18n (default `en`).

## 2. Distribution & global access (mirror mcp-cronos)

- Package name: `mcp-trove`. Module: `mcp_trove`. Layout: `src/mcp_trove/`.
- Entry point: `mcp-trove = "mcp_trove.server:run"`.
- `requires-python >= 3.10`. Dep: `mcp >= 1.0.0` (+ crypto lib, see §6).
- Published to PyPI like `mcp-cronos`.
- Globally available on the machine via a stdio entry in `~/.claude.json`:
  ```json
  "trove": {
    "type": "stdio",
    "command": "uv",
    "args": ["--directory", "/Users/mauriziomocci/Documents/workspace/MCP/trove",
             "run", "mcp-trove"]
  }
  ```
  Same mechanism as Cronos: usable from any project/cwd.
- Reuses the Cronos skeleton: `config`, `i18n`, `template_loader`, bilingual
  README, Keep-a-Changelog CHANGELOG, test discipline.

## 3. Vault layout

```
<trove>/
  snippets/<domain>/<sub>/<slug>.md     # plaintext
  secrets/<category>/<slug>.age          # encrypted (see §6)
  _assets/                               # images, diagrams
  INDEX.md                               # generated from frontmatter
  CONVENTIONS.md                         # entry format contract
  .gitignore                             # excludes key material, temp files
  trove.toml                             # vault config (recipients, language)
```

- Vault path is configurable (env `TROVE_PATH` or `trove.toml`); not hardcoded.
- Domains/categories are user-defined; nothing domain-specific is baked in.
- The git remote (private GitHub) and commit/push are the user's responsibility
  in v1 (see §7).

### Snippet frontmatter (generic)

```yaml
---
title: Human readable title
tags: [domain, concept]
lang: python
type: snippet
project: optional-project-name   # optional, generic
created: 2026-06-29
updated: 2026-06-29
---
```

## 4. Encryption model

- Snippets: plaintext.
- Secrets: encrypted at rest. The private key lives **outside the repo**
  (`~/.config/trove/key`), git-ignored. The public recipient is stored in
  `trove.toml` (committable).
- The server **never implements crypto**; it calls a vetted library/binary.
- Multi-machine: the vault travels via git; the key travels **separately**
  (restored from an off-machine backup). Cloning alone cannot decrypt — by
  design.

## 5. Tools (English, `trove_*`)

| Tool | Input | Effect / Output |
|---|---|---|
| `trove_init` | vault path, age recipient (or generate keypair), language | scaffolds dirs, `trove.toml`, `.gitignore`, pre-commit secret hook, `CONVENTIONS.md`; prints key-backup reminder |
| `trove_add_snippet` | domain, subpath?, title, tags[], lang, body_markdown | creates dirs if missing, writes `<slug>.md` with frontmatter, regenerates INDEX; returns path |
| `trove_add_secret` | category, title, fields{}, notes? | writes encrypted file under `secrets/`, updates INDEX with title+category only (never values); returns path |
| `trove_get_secret` | id/path | decrypts on the fly (needs key present), returns fields; never written to disk |
| `trove_update_secret` | name, category?, set_fields?, remove_fields?, notes?, tags? | decrypts, applies a partial change, re-encrypts; preserves created date; values never written to disk |
| `trove_search` | query, tags?, kind(snippet\|secret\|all) | full-text over snippets, metadata-only over secrets; returns matches |
| `trove_list` / `trove_index` | — | regenerate / read INDEX |
| `trove_remove` | path | deletes entry, regenerates INDEX |
| `trove_doctor` | — | read-only health report: unencrypted secret in repo, broken frontmatter, orphan assets, missing key, files outside convention — each with severity + fix |

## 6. Open decisions — proposed defaults

1. **Crypto backend — [default] `age` via a pip-installable binding
   (`pyrage`)**, so `pip install mcp-trove` is self-contained (no external
   binary required). Alternative: shell out to the `age`/`sops` binaries.
   Rationale: adoption for a public PyPI tool; still vetted crypto, never ours.
2. **License — [default] MIT** (max adoption). Alternative: Apache-2.0 (patent
   clause).
3. **Git — [default] user-owned in v1.** The server manages files only; the
   user runs commit/push. A `trove_sync` tool is deferred to a later version.
4. **`trove_doctor` — [default] included.** For a security-adjacent tool, a
   hygiene/audit command is high value.

## 7. Security guarantees (baked in)

- Crypto delegated to a vetted library; none written here.
- Private key outside the repo and in `.gitignore`.
- `trove_add_secret` encrypts in an out-of-repo temp, then writes only
  ciphertext into the repo — no transient plaintext in the working tree.
- INDEX and search never expose secret values.
- `trove_init` installs a pre-commit secret scanner as an independent safety
  net (defense in depth), auto-enables it when the vault is a git repo, and
  forces a key-backup reminder.
- **Cleartext metadata caveat:** the `.meta.yaml` sidecars (titles, tags,
  categories) are cleartext and travel with the vault. Only secret *values* are
  encrypted. The remote must be private; `trove_doctor` reminds when a remote is
  configured.

## 8. Model-vs-code division

The server is deterministic plumbing. Understanding messy input, choosing
titles/tags, segmenting prose vs code — that is the calling model's job. The
model calls tools with **already-structured** arguments; the server persists
them (placement, frontmatter, encryption, index). Same contract as Cronos.

## 9. Out of scope (v1)

- Automatic git operations (deferred `trove_sync`).
- A reading UI (Obsidian/VS Code already read the plaintext vault).
- Bulk migration engine (handled ad hoc by the model feeding old files through
  `trove_add_snippet`).
- Semantic/embedding search (full-text + tags first).
