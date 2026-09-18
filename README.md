# PaperFlow

PaperFlow turns a Zotero library into clean, durable Markdown notes for Obsidian and Codex.

```text
Zotero  →  PaperFlow  →  Obsidian  →  Codex
 facts   sync · triage   evidence     reasoning
```

It is a small, Windows-first personal tool. Zotero remains the source of truth for papers, metadata, PDFs, and annotations. PaperFlow owns only the clean Markdown sync and the triage that decides which papers deserve deep reading. Codex can then connect literature into concepts, synthesis, questions, and writing.

## Quick Start on Windows

Clone PaperFlow, open PowerShell in the repository, and run one setup command:

```powershell
git clone https://github.com/soren-max/PaperFlow.git
cd PaperFlow
powershell -ExecutionPolicy Bypass -File .\setup-windows.ps1
```

Pass the Vault directly when you already know it:

```powershell
.\setup-windows.ps1 -Vault "E:\Obsidian\Research"
```

The setup script finds Python 3.12+, creates or reuses `.venv`, installs PaperFlow, starts Zotero when needed, initializes `zotero-agent`, finds your Obsidian Vault, runs `paperflow init` and `doctor`, and checks Codex CLI. If Codex is missing, it offers the current official OpenAI Windows installer.

The script adds only this repository's `.venv\Scripts` directory to your **user** PATH—never the system PATH. After the first setup, open a new PowerShell window once so it sees the updated PATH. The daily workflow is then:

```powershell
paperflow sync
cd "E:\Obsidian\Research"
codex
```

Use `-SkipCodex` or `-SkipZotero` when you intentionally want to configure that part later. Re-running setup is safe: the virtual environment and existing PaperFlow configuration are reused, while your customized Vault instructions and templates remain untouched.

## Advanced / Manual Setup

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
00-Research-Areas/
01-Literature/
02-Concepts/
03-Synthesis/
04-Questions/
90-Templates/
  ResearchArea.md
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
paperflow triage
paperflow status
paperflow doctor
```

Running `paperflow` with no command is the same as `paperflow status`.

- `sync` reads regular items and PDF annotations from the selected Zotero scope.
- `triage` prepares bounded packets for synced papers and reports which ones deserve deep processing.
- `status` shows the active scope, Zotero papers, synced/pending notes, new annotations, triage and processing counts, and the last sync.
- `doctor` checks configuration, Vault, Zotero bridge, Codex, and Git, with a direct fix when something is wrong.

## Using PaperFlow with Codex

Sync, open Codex in the Vault, and ask naturally:

```powershell
paperflow sync
codex
```

- Triage the synced papers and tell me which ones are worth reading deeply.
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

## Triage the backlog

Deep reading is expensive, so not every synced paper should get it. `triage` is the cheap first pass that decides:

```powershell
paperflow triage             # the backlog, up to --limit papers
paperflow triage jiangndkg   # one paper
```

The command builds a bounded `.paperflow/triage/<zotero-key>/packet.md` from the Literature note, brief relevant Research Areas and Questions, linked knowledge notes, and existing reading and processing state. It reads no PDF, needs no Zotero connection, and no converter. Then, in Codex, the skill reads `prompts/triage.md` and writes `paper-card.md` beside the packet:

```markdown
---
paperflow_card: 1
citekey: jiangndkg
zotero_key: J68KBEZ6
research_area: KG-augmented RAG
priority: high
processing_level: deep
basis: abstract, tags
---
```

Rerun `paperflow triage` to validate the card and save its state. `priority` (`low`/`medium`/`high`) describes research value; `processing_level` (`triage_only`/`quick`/`normal`/`deep`) describes warranted reading depth. `reading_status` and `processing_status` distinguish a valuable paper from work that still needs doing. Older cards with `deep_processing` remain valid. A card is a routing decision, not a summary: five sections, each under 80 words, and the CLI rejects an invalid field, an unsupported input, or a card for another paper. Repeated runs order still-pending papers first.

Keep `00-Research-Areas/` and `04-Questions/` current: their brief content informs relevance. A `deep` card merits the staged workflow when its processing status is still `unprocessed` or `triaged`. The [V3 triage report](docs/v3-triage.md) records the packet contract and the context budget.

## V2 staged reading spike

The V1 daily commands remain the same. For a high-value paper with a local Zotero PDF, install the optional PDF converter and ingest a synced citekey:

```powershell
python -m pip install -e ".[pdf]"
paperflow ingest jiangndkg
paperflow process jiangndkg
```

`ingest` keeps the PDF in Zotero and creates page-marked `source.md`, `structure.json`, and `state.json` under the Vault's `.paperflow/papers/<zotero-key>/`. `process` shows the next durable reading stage. The installed PaperFlow Codex skill uses versioned prompts to build a paper map, read one bounded section at a time, validate evidence cards, build method/result cards, and publish a compressed reading block before `## My Notes`. `paperflow process <citekey> --section <id>` lists that section's chunks; `--publish-note` publishes only after validation. Repeating `process` resumes from the saved artifacts.

PyMuPDF4LLM is the current default converter. Use `python -m pip install -e ".[pdf-docling]"` and `paperflow ingest <citekey> --converter docling` for the Docling alternative on a fresh paper. The [converter ADR](docs/adr/pdf-to-markdown.md) gives the KG-Agent benchmark, accuracy limits, and license details. The [V2 spike report](docs/v2-spike.md) records the data flow and acceptance result.

## Migrating an existing research note

Run `paperflow migrate <citekey>` before processing one existing note. It records a fixed baseline for `## My Notes` and linked Concept, Question and Synthesis files, then reports drift and V2 progress on later runs. Build the staged evidence and compare the old claims in `.paperflow/migrations/<zotero-key>/migration-review.md` before publishing a V2 reading block. The [legacy migration strategy](docs/legacy-migration.md) describes the state schema, reconcile rules and BRINK/KG-Agent validation.

## Development

```powershell
python -m pip install -e ".[dev]"
pytest
ruff check .
```

The tests focus on repeatable sync, metadata and annotation updates, preserved personal notes, valid manifests, readable Markdown, and reproducible triage packets and cards.
