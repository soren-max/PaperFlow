# Long-Research Integration & Workflow Guide

> Target pattern: an 8-week Codex-mentored research workspace (`research/` + `experiments/`) connected read-only to a PaperFlow Vault (`00-Research-Areas/` .. `90-Templates/`).

## 1. Design Principles

1. **No premature bulk initialization**: PaperFlow does not auto-initialize `.paperflow/` or batch-read PDFs when Zotero is populated by Stage A (`import_zotero_literature.py`).
2. **Portable configuration**: Use `.paperflow/config.toml` relative paths (or environment-expanded paths) instead of hardcoding user paths in source code. See [`docs/examples/long_research.config.toml`](examples/long_research.config.toml).
3. **Read-only program awareness**: PaperFlow reads Codex-maintained files in `research/` and `experiments/` without modifying them.
4. **Windows Zotero + WSL Markdown compatibility**:
   - `zotero_backend = "auto"` tries `zotero-agent` bridge first and falls back to Zotero's built-in read-only Local HTTP API (`http://127.0.0.1:23119/api/users/0/...`), which works directly from WSL as well as Windows.
   - `ingest` and `migrate` translate Windows PDF locators (`C:\Users\...` or `file:///C:/...`) into `/mnt/c/...` automatically when running on WSL.

---

## 2. Recognized Files & Bidirectional Links (`Paper ↔ RQ ↔ Hypothesis ↔ Experiment`)

When `research_dir` (default auto-detected `<vault>/research`) and `experiments_dir` (default `<vault>/experiments`) exist:

| Source | Ownership | What PaperFlow Reads (Read-Only) |
|---|---|---|
| `research/RESEARCH_HOME.md`, `RESEARCH_STATE.md` | Codex / Researcher | Active week (`Week N`) and current research focus |
| `research/READING_ROADMAP.md` | Codex | `RQ-01` .. `RQ-08` rows, required/optional reading, weekly deliverables |
| `research/HYPOTHESIS_REGISTRY.md` | Codex / Researcher | Hypothesis IDs (`H01`, ...), statements, falsification criteria |
| `research/IDEA_BOARD.md` | Codex / Researcher | Candidate directions and states (`Exploration`, `Validation`, ...) |
| `research/EXPERIMENT_LEDGER.md` | Codex / Researcher | Logged runs, linked RQs, hypotheses, baselines, status |
| `research/papers.jsonl` | Import script / Codex | Pre-curated Zotero item keys, DOIs, weeks, priorities, RQ mappings |
| `experiments/reports/*.md` | Codex / Researcher | Frontmatter (`experiment_id`, `rq_ids`, `hypothesis_ids`, `baseline_papers`, `challenged_papers`, `failure_modes`) and inline `[[citekey]]` / `Hxx` / `RQ-xx` links |
| `01-Literature/*.md` | PaperFlow (`sync`) & Researcher (`manual-*`, `## My Notes`) | Synced Zotero notes + detection of `manual-*.md` cards matching Zotero item keys or DOIs |
| `03-Synthesis/*.md`, `04-Questions/*.md` | Researcher / Agent | `Positioning.md` (`rq_ids`, `hypothesis_ids`, `experiment_ids`, `baseline_for`, `challenged_by_experiments`), `NoveltyLedger.md`, `Question.md` |

---

## 3. CLI Inspection & Cross-Directory Search

Daily work remains `paperflow sync` plus natural-language requests. Three lightweight inspection/search helpers are available when needed:

```bash
# 1. Status panel (adds a single compact Research row when research/ exists)
paperflow status --vault /path/to/vault

# 2. Read-only program summary (week, RQs, hypotheses, experiments, manual-note matches)
paperflow research --vault /path/to/vault
paperflow research --vault /path/to/vault --json

# 3. Cross-directory lookup (no DB, no vector store)
paperflow find RQ-01 --vault /path/to/vault
paperflow find H01 --vault /path/to/vault
paperflow find cemri2025mast --vault /path/to/vault
paperflow find EXP-001 --vault /path/to/vault
paperflow find "condition dropped" --type evidence --vault /path/to/vault
paperflow find "" --type competitor --vault /path/to/vault
```

---

## 4. Synthetic Integration Demo (Non-Destructive, No Real Zotero Writes)

> **Important (Synthetic Demo Notice)**: The walkthrough below uses synthetic demo fixtures (matching `tests/test_academic_workflow.py::test_research_integration_links_papers_rqs_hypotheses_experiments_and_preserves_files`) and does **not** claim real empirical findings or modify Zotero or `long_research`.

### Step-by-step trace (`RQ → Paper → Evidence → Hypothesis → Experiment → Next Question`)

1. **Start from the active Research Question (`research/READING_ROADMAP.md`)**:
   - `RQ-01`: *How do handoff failures arise in MAS?* (mapped to Week 1).
2. **Locate matching synced & manual literature (`paperflow find RQ-01`)**:
   - Finds corpus entry `cemri2025mast` (`zotero_key: 4TM5XREY`, `priority: Core`) and detects existing `01-Literature/manual-cemri2025mast.md` alongside synced `01-Literature/cemri2025mast.md` without altering `## My Notes`.
3. **Locate verified PDF evidence (`.paperflow/papers/4TM5XREY/evidence.jsonl`)**:
   - `paperflow find "condition dropped" --type evidence` locates evidence card `[E001]` at page 4 (`source_chunk: sections/01-intro-01.md`), preserving exact quote provenance.
4. **Connect Paper to Hypothesis (`03-Synthesis/cemri2025mast-Positioning.md` + `HYPOTHESIS_REGISTRY.md`)**:
   - Positioning Card links `rq_ids: [RQ-01]`, `hypothesis_ids: [H01]`, `baseline_for: [EXP-001]`, `inference: true`, `source_sha256`, and `evidence_sha256`.
   - `paperflow find H01 --json` returns:
     - `hypotheses`: `H01` (*Short handoffs drop scope constraints before downstream decisions*)
     - `papers`: `[[cemri2025mast]]` (with `evidence_count: 1`, `baseline_for: ["EXP-001"]`)
     - `evidence`: `[E001]` (page 4)
     - `experiments`: `EXP-001`
5. **Trace Experiment Impact (`experiments/reports/EXP-001.md`)**:
   - Synthetic demo report `EXP-001` records `baseline_papers: [cemri2025mast]`, `challenged_papers: [agent2026]`, `failure_modes: [condition_dropped]`.
   - `paperflow find EXP-001` surfaces both the baseline dependency (`cemri2025mast`) and the challenged assumption (`agent2026` → `challenged_by_experiments: ["EXP-001"]`).
6. **Generate the Next Decision Question (`04-Questions/`)**:
   - From the remaining uncertainty in `Positioning` + `EXP-001`, record a concrete decision Question linking `[[cemri2025mast]]`, `[[agent2026]]`, `RQ-01`, `H01`, and `EXP-001`, specifying what counterfactual intervention will settle it in Week 4.

---

## 5. Preserving Existing `long_research` Notes When Starting Paper 1

When you later choose to run PaperFlow for the first time inside a research workspace:
1. Keep `collection_keys = ["JSQ9B7XW"]` (scoped to `Research-8Weeks`, never Entire Library unless desired).
2. Keep `01-Literature/manual-cemri2025mast.md` untouched during initial `paperflow sync`.
3. When reading `cemri2025mast` deeply, `paperflow research` flags the `manual-cemri2025mast.md -> [[cemri2025mast]]` match so you can migrate `## My Notes` into `01-Literature/cemri2025mast.md` intentionally once and retire the `manual-` duplicate.
