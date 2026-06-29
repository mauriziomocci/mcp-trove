# mcp-trove

An MCP server that manages a **trove**: a git-backed vault holding two kinds of
entry — plaintext **snippets** (searchable Markdown, with images and diagrams)
and **secrets** stored **encrypted at rest**, so the whole vault can be pushed to
a private remote without exposing them. A trove holds both treasures (secrets)
and finds (snippets).

The server is the deterministic writer over the vault: the calling model composes
and cleans content, the server guarantees placement, slug, frontmatter,
encryption and index — always the same, no drift.

## Install

```bash
pip install mcp-trove        # or: uv add mcp-trove
```

`pip install` is self-contained — encryption uses the `age` algorithm through the
`pyrage` binding, so no external binary is required.

## Configure

The vault root comes from the `TROVE_PATH` environment variable. Register the
server with your MCP client (Claude Code shown):

```json
"trove": {
  "type": "stdio",
  "command": "uv",
  "args": ["--directory", "/path/to/mcp-trove", "run", "mcp-trove"],
  "env": { "TROVE_PATH": "/path/to/your/trove" }
}
```

Then call `trove_init` once to scaffold the vault and generate the age keypair.
The private key is written outside the repo (default `~/.config/trove/key`); the
public recipient is committed in `trove.toml`.

> **Back up your private key off-machine** (e.g. a password manager). Without it
> the encrypted secrets are unrecoverable, even for you. On a new machine you
> clone the git vault and restore the key separately — cloning alone cannot
> decrypt, by design.

## Key management

There are two keys, and only one is secret.

- **Public recipient** (`age1...`) — committed in `trove.toml` under
  `recipients`. Secrets are *encrypted to* it. Safe to share.
- **Private key** (`AGE-SECRET-KEY-1...`) — *decrypts* secrets. Never commit it.

**Where it lives.** Trove looks for the private key in this order:

1. `TROVE_KEY_PATH` environment variable, if set.
2. `key_path` under `[trove]` in `trove.toml`, if set.
3. Default: `~/.config/trove/key`.

**File format.** A plain text file containing a single `AGE-SECRET-KEY-1...`
line (lines starting with `#` are ignored). Keep it `chmod 600`.

**Creating it.** `trove_init` generates the keypair on first run: it writes the
private key to the resolved path (mode 600) and records the public recipient in
`trove.toml`. You don't create it by hand.

**Backing it up.** Copy that single file somewhere off this machine — your
password manager is ideal. This is the only thing that cannot be regenerated.

**Restoring on another machine.**

```bash
mkdir -p ~/.config/trove
# paste your backed-up key into the file, one AGE-SECRET-KEY-1... line:
$EDITOR ~/.config/trove/key
chmod 600 ~/.config/trove/key
git clone <your-private-vault-repo> /path/to/your/trove   # the snippets + encrypted secrets
export TROVE_PATH=/path/to/your/trove
```

The git clone brings the vault (snippets and encrypted secrets); the key file
brings the ability to decrypt. With both in place, `trove_get_secret` works.

## Reading secrets without the MCP

The MCP is a convenience, not a lock-in. The package ships a `trove` command
alongside the server, so you can read and browse the vault straight from a
terminal — no MCP client running, and no external `age` binary (decryption goes
through the bundled `pyrage`). It reads the same `TROVE_PATH` and private key the
server uses.

```bash
trove get jira                      # decrypt and print all fields
trove get jira --field password     # print one raw value (pipe-friendly)
trove get jira --field password --clip   # copy to clipboard, keep it off-screen
trove get jira --json               # machine-readable dump
trove list                          # list every entry
trove search grafana --kind secret  # search (metadata only for secrets)
```

`--clip` shells out to the platform clipboard tool (`pbcopy`, `wl-copy`, `xclip`,
`xsel`, or `clip`); if none is present it errors instead of printing.

As a low-level fallback, secrets are plain `age` files (ASCII-armored,
`-----BEGIN AGE ENCRYPTED FILE-----`), so the standard `age` CLI decrypts them
too:

```bash
age -d -i ~/.config/trove/key <trove>/secrets/<category>/<slug>.age
```

`rage` (the Rust implementation) works the same way. Security lives entirely in
the private key, not in the server: whoever holds `~/.config/trove/key` can read
every secret, with or without the MCP.

Note on Markdown readers (Obsidian, etc.): the `secrets/` folder looks **empty**
because those tools list only `.md` files, and secrets are `.age` payloads plus
`.meta.yaml` sidecars. The files are there — enable "Detect all file extensions"
to see them. The `.age` stays unreadable (encrypted) and the `.meta.yaml` shows
only title and tags, never values. Use Markdown readers for `snippets/`; manage
secrets through the MCP tools or the `age` CLI.

## Tools

| Tool | Purpose |
|---|---|
| `trove_init` | Scaffold the vault, generate/register the keypair, write config, hooks |
| `trove_add_snippet` | Save a plaintext snippet (Markdown + frontmatter) |
| `trove_add_secret` | Save an encrypted secret + cleartext metadata sidecar |
| `trove_get_secret` | Decrypt a secret on the fly (needs the private key) |
| `trove_update_secret` | Partially update a secret (set/remove fields, notes, tags) and re-encrypt |
| `trove_search` | Full-text over snippets; metadata-only over secrets |
| `trove_list` / `trove_index` | List entries / regenerate `INDEX.md` |
| `trove_remove` | Delete an entry and rebuild the index |
| `trove_doctor` | Read-only health & safety audit |

## Layout

```
<trove>/
  snippets/<domain>/<sub>/<slug>.md     plaintext markdown + frontmatter
  secrets/<category>/<slug>.age          encrypted payload (armored age)
  secrets/<category>/<slug>.meta.yaml    cleartext metadata, never values
  _assets/                               images, diagrams
  INDEX.md                               generated
  trove.toml                             vault config (recipients, language)
```

Snippets render in any Markdown reader (Obsidian, VS Code, GitHub). The index and
search read only cleartext metadata for secrets, so they can never leak a value.

## Security model

- Encryption is delegated to vetted code (`age`/`pyrage`); none is written here.
- The private key lives outside the repo and is git-ignored.
- `trove_add_secret` encrypts in memory; plaintext never touches disk.
- `trove_init` installs a pre-commit hook that blocks committing a private key,
  and enables it automatically (`core.hooksPath`) when the vault is a git repo.
- `trove_doctor` flags any cleartext under `secrets/` or a key in the tree, and
  reminds you when a git remote is configured.

**Cleartext metadata caveat.** Secret *values* are encrypted, but the
`.meta.yaml` sidecars — titles, tags, category names — are cleartext and get
pushed with the vault. Keep the remote **private** and avoid putting sensitive
details in secret titles (prefer "Prod DB" over "Prod DB root password h***").

## Development

```bash
uv sync --extra dev
uv run pytest
uv run ruff check src tests
```

---

# mcp-trove (Italiano)

Server MCP che gestisce un **trove**: un vault versionato con git che contiene due
tipi di voce — **snippet** in chiaro (Markdown cercabile, con immagini e schemi) e
**segreti** salvati **cifrati a riposo**, così l'intero vault si pubblica su un
remote privato senza esporli. Un trove custodisce sia i tesori (i segreti) sia i
ritrovamenti (gli snippet).

Il server è lo scrittore deterministico del vault: il modello compone e ripulisce
il contenuto, il server garantisce collocazione, slug, frontmatter, cifratura e
indice — sempre uguali, senza deriva.

## Installazione

```bash
pip install mcp-trove
```

L'installazione è autosufficiente: la cifratura usa l'algoritmo `age` tramite il
binding `pyrage`, nessun binario esterno richiesto.

## Configurazione

La radice del vault arriva dalla variabile d'ambiente `TROVE_PATH`. Registra il
server nel tuo client MCP (esempio Claude Code) come mostrato sopra, poi chiama
`trove_init` una volta per creare il vault e generare la coppia di chiavi age.

> **Fai un backup della chiave privata fuori dalla macchina** (es. password
> manager). Senza, i segreti cifrati sono irrecuperabili, anche per te. Su un PC
> nuovo cloni il vault git e ripristini la chiave a parte: clonare e basta non
> decifra, per scelta.

## Gestione della chiave

Le chiavi sono due, e solo una è segreta.

- **Recipient pubblico** (`age1...`) — committato in `trove.toml` sotto
  `recipients`. I segreti vengono *cifrati verso* di lui. Si può condividere.
- **Chiave privata** (`AGE-SECRET-KEY-1...`) — *decifra* i segreti. Mai committarla.

**Dove vive.** Trove cerca la chiave privata in quest'ordine:

1. variabile d'ambiente `TROVE_KEY_PATH`, se impostata;
2. `key_path` sotto `[trove]` in `trove.toml`, se impostato;
3. default: `~/.config/trove/key`.

**Formato del file.** Un file di testo con una sola riga `AGE-SECRET-KEY-1...`
(le righe che iniziano con `#` sono ignorate). Tienilo a `chmod 600`.

**Creazione.** `trove_init` genera la coppia al primo avvio: scrive la chiave
privata nel path risolto (permessi 600) e registra il recipient pubblico in
`trove.toml`. Non la crei a mano.

**Backup.** Copia quel singolo file fuori da questa macchina — il password
manager è il posto ideale. È l'unica cosa che non si può rigenerare.

**Ripristino su un'altra macchina.**

```bash
mkdir -p ~/.config/trove
# incolla la chiave salvata nel file, una riga AGE-SECRET-KEY-1...:
$EDITOR ~/.config/trove/key
chmod 600 ~/.config/trove/key
git clone <repo-privato-del-vault> /path/to/your/trove   # snippet + segreti cifrati
export TROVE_PATH=/path/to/your/trove
```

Il clone git porta il vault (snippet e segreti cifrati); il file chiave porta la
capacità di decifrare. Con entrambi a posto, `trove_get_secret` funziona.

## Leggere i segreti senza l'MCP

L'MCP è una comodità, non un vincolo. Il package installa un comando `trove`
accanto al server, così leggi e navighi il vault direttamente da terminale —
senza client MCP attivo e senza binario `age` esterno (la decifratura passa per
`pyrage` già incluso). Usa lo stesso `TROVE_PATH` e la stessa chiave privata del
server.

```bash
trove get jira                      # decifra e stampa tutti i campi
trove get jira --field password     # stampa un solo valore grezzo (per pipe)
trove get jira --field password --clip   # copia negli appunti, fuori dallo schermo
trove get jira --json               # output leggibile dalle macchine
trove list                          # elenca ogni voce
trove search grafana --kind secret  # cerca (solo metadata per i segreti)
```

`--clip` invoca il tool clipboard di sistema (`pbcopy`, `wl-copy`, `xclip`,
`xsel` o `clip`); se non ce n'è nessuno dà errore invece di stampare.

Come fallback di basso livello, i segreti sono normali file `age` (in armor
ASCII, `-----BEGIN AGE ENCRYPTED FILE-----`), quindi anche la CLI standard `age`
li decifra:

```bash
age -d -i ~/.config/trove/key <trove>/secrets/<categoria>/<slug>.age
```

Anche `rage` (l'implementazione Rust) funziona allo stesso modo. La sicurezza sta
tutta nella chiave privata, non nel server: chi possiede `~/.config/trove/key`
legge ogni segreto, con o senza l'MCP.

Nota sui lettori Markdown (Obsidian, ecc.): la cartella `secrets/` appare
**vuota** perché quegli strumenti elencano solo i file `.md`, mentre i segreti
sono payload `.age` più sidecar `.meta.yaml`. I file ci sono — attiva "Detect all
file extensions" per vederli. Il `.age` resta illeggibile (cifrato) e il
`.meta.yaml` mostra solo titolo e tag, mai i valori. Usa i lettori Markdown per
gli `snippets/`; i segreti gestiscili con gli strumenti MCP o con la CLI `age`.

## Modello di sicurezza

- La cifratura è delegata a codice collaudato (`age`/`pyrage`), nessuna scritta
  qui.
- La chiave privata vive fuori dal repo ed è esclusa da git.
- `trove_add_secret` cifra in memoria; il testo in chiaro non tocca mai il disco.
- `trove_init` installa un hook pre-commit che blocca il commit di una chiave
  privata e lo abilita da solo (`core.hooksPath`) quando il vault è un repo git.
- `trove_doctor` segnala qualsiasi file in chiaro sotto `secrets/` o una chiave
  nell'albero, e ti avvisa quando è configurato un remote git.

**Caveat metadati in chiaro.** I *valori* dei segreti sono cifrati, ma i sidecar
`.meta.yaml` — titoli, tag, nomi di categoria — sono in chiaro e vengono pushati
col vault. Tieni il remote **privato** ed evita dettagli sensibili nei titoli
(meglio "Prod DB" che "Prod DB password di root h***").
