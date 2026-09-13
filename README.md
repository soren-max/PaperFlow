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

PaperFlow talks only to the local bridge and does not require a Zotero cloud account. If `zot init` cannot detect a `userID` but `paperflow doctor` says `Zotero reachable`, PaperFlow is ready to use.

Better BibTeX is optional but recommended. When available, PaperFlow uses its stable citation keys. Without it, PaperFlow creates a readable key once and preserves it in the manifest.

## First run

If Obsidian already knows about one Vault, PaperFlow discovers it. When Zotero is connected, initialization also offers an optional collection picker:

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
90-Templates/
  Concept.md
  Synthesis.md
  Question.md
.agents/
  skills/paperflow/SKILL.md
AGENTS.md
.paperflow/
  config.toml
  manifest.json
```

Existing folders, customized instructions, skills, and templates are left untouched. Re-running `init` upgrades the original PaperFlow-generated instructions and adds missing V1.2 resources. PaperFlow remembers the active Vault so daily commands work from any directory.

### Zotero scope

The default is **Entire Library**. You can instead select one or more Zotero collections during `paperflow init`. Run `paperflow init` again whenever you want to change the selection.

- PaperFlow stores stable Zotero collection keys, so renaming a collection does not break the configuration.
- Selecting a collection includes all of its nested collections, matching the intuitive recursive behavior of `zotero-agent export --recursive`.
- Selecting overlapping parent and child collections never duplicates a paper.
- An empty collection is a valid scope and produces zero selected papers.
- Existing V1 configuration files automatically mean Entire Library; no migration command is needed.

## Daily use

```powershell
paperflow sync
paperflow status
paperflow doctor
```

Running `paperflow` with no command is the same as `paperflow status`.

- `sync` reads regular items and PDF annotations from the selected Zotero scope.
- `status` shows the active scope, Zotero papers, synced/pending notes, new annotations, and the last sync.
- `doctor` checks configuration, Vault, Zotero bridge, Codex, and Git, with a direct fix when something is wrong.

## Using PaperFlow with Codex

Sync, open Codex in the Vault, and ask naturally:

```powershell
paperflow sync
codex
```

- Review my recently synced papers.
- Synthesize the literature on agent memory.
- Update the concept note for retrieval-augmented generation.
- What should I read next based on my open questions?

The included PaperFlow skill teaches Codex to keep Literature as source-grounded evidence and put cross-paper reasoning in Concepts or Synthesis while retaining citekeys. PaperFlow provides no AI runtime of its own; Codex works directly on the human-readable Markdown Vault.

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

The manifest maps each Zotero item key to its stable citekey and note path. Changing scope does not delete notes that were synced earlier. PaperFlow never writes to Zotero and does not use a database.

## Development

```powershell
python -m pip install -e ".[dev]"
pytest
ruff check .
```

The tests focus on repeatable sync, metadata and annotation updates, preserved personal notes, valid manifests, and readable Markdown.
