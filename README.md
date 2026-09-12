# PaperFlow

PaperFlow turns a Zotero library into clean, durable Markdown notes for Obsidian and Codex.

```text
Zotero  →  PaperFlow  →  Obsidian  →  Codex
 facts       sync        knowledge     reasoning
```

It is a small, Windows-first personal tool. Zotero remains the source of truth for papers, metadata, PDFs, and annotations. PaperFlow owns only the clean Markdown sync. Codex can then connect literature into concepts, synthesis, questions, and writing.

## Install

Python 3.12 or newer is required.

```powershell
python -m pip install -e .
```

PaperFlow uses [zotero-agent](https://github.com/alex-roc/zotero-agent) for local Zotero access. Open Zotero and initialize the bridge connection once:

```powershell
zot init
```

If the bridge plugin is not installed yet, `zot init` prints its official download link and the short Zotero installation steps. Run `zot init` again after installing the XPI.

Better BibTeX is optional but recommended. When available, PaperFlow uses its stable citation keys. Without it, PaperFlow creates a readable key once and preserves it in the manifest.

## First run

If Obsidian already knows about one Vault, PaperFlow discovers it:

```powershell
paperflow init
```

Or provide a path, including paths with spaces or Chinese characters:

```powershell
paperflow init "E:\Notes\Research"
```

Initialization creates only:

```text
01-Literature/
02-Concepts/
03-Synthesis/
04-Questions/
AGENTS.md
.paperflow/
  config.toml
  manifest.json
```

Existing folders and `AGENTS.md` are left untouched. PaperFlow remembers the active Vault so daily commands work from any directory.

## Daily use

```powershell
paperflow sync
paperflow status
paperflow doctor
```

Running `paperflow` with no command is the same as `paperflow status`.

- `sync` reads all regular items and PDF annotations from the personal Zotero library.
- `status` shows Zotero, Vault, synced/pending notes, new annotations, and the last sync.
- `doctor` checks configuration, Vault, Zotero bridge, Codex, and Git, with a direct fix when something is wrong.

## Note ownership

Literature notes use the citation key as the filename, for example `01-Literature/vaswani2017attention.md`. YAML frontmatter and two visible blocks are managed by PaperFlow:

```markdown
<!-- paperflow:begin metadata -->
...
<!-- paperflow:end metadata -->

<!-- paperflow:begin annotations -->
...
<!-- paperflow:end annotations -->
```

Everything under `## My Notes` belongs to you and is preserved across repeated syncs. Do not remove the managed markers; they make updates simple and transparent instead of relying on a merge engine.

The manifest maps each Zotero item key to its stable citekey and note path. PaperFlow never writes to Zotero and does not use a database.

## Development

```powershell
python -m pip install -e ".[dev]"
pytest
ruff check .
```

The tests focus on repeatable sync, metadata and annotation updates, preserved personal notes, valid manifests, and readable Markdown.
