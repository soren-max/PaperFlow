# PaperFlow Academic Workflow Audit

> Audit date: 2026-11-18  
> Audited checkout: `/home/soren/projects/PaperFlow` (`v0.1.4`, `main` commit `ba0760d`)  
> Target research workspace inspected (read-only): `/home/soren/projects/idea_1117/long_research`  
> Policy: **Reuse > Configure > Extend > Rewrite**

## 1. Executive Summary

PaperFlow `0.1.4` already implements most of the core literature-to-knowledge infrastructure required for an evidence-grounded research program:

- **V1**: Idempotent Zotero metadata/annotation synchronization into `01-Literature/<citekey>.md`, stable Better BibTeX or fallback citekeys, `manifest.json`, recursive/deduplicated Zotero collection scopes, and strict preservation of `## My Notes`.
- **V2**: Staged PDF ingestion (`pymupdf4llm` / `docling`), page-marked `source.md`, `structure.json`, bounded `<= 12,000`-character section chunks, deterministic quote-and-page evidence validation (`evidence/<section-id>.jsonl`), method/result cards, `paper-note.md`, `--publish-note` insertion before `## My Notes`, and `migrate` legacy baseline/drift checks.
- **V3**: Offline bounded triage (`triage.py`, packet `<= 28,000` chars, context digest `<= 12,000` chars, `reading_status` + `processing_status`, stale detection when notes or context change).
- **V4**: Contribution-centered positioning (`positioning.py`, `Positioning.md`, `NoveltyLedger.md`, `Question.md`, `ResearchArea.md`, SHA-256 provenance checks on `source.md` and `evidence.jsonl`, explicit `inference: true` boundary).
- **Packaging & Upgrades**: `cli.py` + `resource-upgrades.json` upgrades unmodified Vault instructions, prompts, skills, and templates by LF-normalized SHA-256 while preserving customized user files byte-for-byte.

Accordingly, **no core rewrite is needed**. Only targeted extensions are warranted where real environment or cross-program gaps exist.

---

## 2. Source Code & Environment Findings

### 2.1 `pyproject.toml`, CLI, and Tests
- Package `paperflow` `0.1.4` (`Python >= 3.12`), CLI entrypoint `paperflow = "paperflow.cli:app"` (`init`, `sync`, `ingest`, `triage`, `process`, `migrate`, `status`, `doctor`).
- Core dependencies: `PyYAML`, `questionary`, `rich`, `typer`, `zotero-agent>=0.8.5,<0.9`; optional extras: `dev`, `pdf` (`pymupdf4llm`), `pdf-docling` (`docling`).
- Test baseline: with `.[dev,pdf]` installed (and clean `PYTHONPATH`), `pytest` runs **80 passed, 4 skipped** (`tests/test_wsl_bridge.py` skips on Linux because it invokes Windows `wsl.exe`) and `ruff check .` passes cleanly.
- Observation in `src/paperflow/ingest.py:206`: `version(converter)` raises `PackageNotFoundError` when `pymupdf4llm` is absent even if `_pymupdf_pages` is mocked in tests; runtime PDF conversion properly requires `paperflow[pdf]` or `paperflow[pdf-docling]`.

### 2.2 Zotero Connectivity & Windows/WSL Reality
- `src/paperflow/zotero.py` currently relies exclusively on `python -m zotero_agent exec -`, which requires the third-party `zotero-agent` bridge XPI plugin and `zot init` configuration.
- Inspection of this machine's real environment confirmed:
  - `E:\zotero` (`/mnt/e/zotero`) is the Zotero 10.0.8 **application** directory (`zotero.exe`), not the database directory.
  - Zotero's active data directory is `C:\Users\soren\Zotero` (`/mnt/c/Users/soren/Zotero`), storing `zotero.sqlite` and `storage/`.
  - Zotero 10.0.8 exposes its built-in **Local HTTP API** on `http://127.0.0.1:23119/api/users/0/...`, which is directly reachable from WSL (with `Connection: close`), and already contains `Research-8Weeks` (`JSQ9B7XW`) and 6 thematic subcollections.
  - Meanwhile, the `zotero-agent` bridge plugin is **not configured** (`zot ping` returns `No token configured`), and `long_research/research/ZOTERO_WORKFLOW.md` already uses the Local HTTP API directly.
- Additionally, `ingest.py` (`Path(entry["path"]).is_file()`) and `migration.py` (`Path(source_state["pdf_locator"]).is_file()`) do not translate Windows drive paths (`C:\Users\...`) or `file:///C:/...` URIs into `/mnt/c/...` when PaperFlow runs inside WSL.
- `tools/paperflow-wsl` (`docs/wsl-bridge.md`) assumes a Windows-hosted Vault (`E:\...`) and intentionally rejects Linux-only Vault paths (`\\wsl.localhost\...` or `/home/...`). Because `/home/soren/projects/idea_1117/long_research` lives on the WSL filesystem, a WSL-native `paperflow` invocation needs read-only Zotero Local HTTP API fallback and Windows-to-WSL PDF path translation, while keeping `tools/paperflow-wsl` unchanged for Windows Vaults.

### 2.3 Research Vault & Existing 8-Week Training Workspace
- `/home/soren/projects/idea_1117/long_research` already contains PaperFlow-compatible folders (`00-Research-Areas/`, `01-Literature/`, `02-Concepts/`, `03-Synthesis/`, `04-Questions/`, `90-Templates/` copied from PaperFlow `0.1.4`) alongside Codex-managed research program files (`research/RESEARCH_HOME.md`, `research/EIGHT_WEEK_ROADMAP.md`, `research/READING_ROADMAP.md`, `research/RESEARCH_STATE.md`, `research/IDEA_BOARD.md`, `research/HYPOTHESIS_REGISTRY.md`, `research/EXPERIMENT_LEDGER.md`, `research/LITERATURE_CORPUS.md`, `research/papers.jsonl`, `research/weekly/week01/PLAN.md`) and `experiments/` (`configs/`, `data/`, `results/`, `traces/`, `reports/`).
- `long_research/docs/PAPERFLOW_SETUP.md` deliberately left `.paperflow/` uninitialized so batch sync/processing does not occur prematurely before per-paper reading begins.
- `01-Literature/manual-cemri2025mast.md` already exists as a manual reading note with `## My Notes` and Zotero item key `4TM5XREY`.

---

## 3. Capability Audit Matrix

| Capability | Existing | Gap | Decision |
|---|---|---|---|
| Zotero 同步 | `zotero.py` + `sync.py` + `markdown.py`: stable citekeys, `manifest.json`, recursive/dedup collection scopes, `## My Notes` & managed block preservation | Only calls `zotero-agent` bridge (`exec -`); cannot read Zotero Local HTTP API (`127.0.0.1:23119`) when bridge plugin is absent | **Extend**: keep `zotero-agent` primary; add read-only Zotero Local HTTP API fallback & configurable `zotero_backend` (`auto`/`bridge`/`local_api`) |
| 文献筛选 | `triage.py`: offline bounded packet (`packet.md`), v1/v2 `paper-card.md`, `reading_status`/`processing_status`, context-change staleness | `context_digest` only sees `00-Research-Areas/`, `04-Questions/`, `03-Synthesis/`; blind to external `research/` roadmaps/hypotheses & `manual-*` cards | **Reuse + Extend**: preserve V3 contract; optionally inject bounded external `research_dir` summary & manual-note hints into `context_digest` |
| PDF 证据读取 | `ingest.py` + `process.py`: page-marked `source.md`, `structure.json`, 12k chunks, quote/page-verified `evidence.jsonl`, cards, `--publish-note` | `ingest.py` / `migration.py` fail on Windows PDF paths (`C:\...` or `file:///C:/...`) when run from WSL; no optional mentor-style reading template | **Reuse + Extend**: add portable Windows/WSL path translation; add optional `90-Templates/MentorReading.md` (P2) |
| 研究假设关联 | `04-Questions/` (`Question.md`), `03-Synthesis/` (`Positioning.md`, `NoveltyLedger.md`), `target_contributions`, `focus_questions` | No explicit `rq_ids`, `hypothesis_ids`, `experiment_ids`, `baseline_for`, or `challenged_by_experiments` links, nor `Paper → RQ → Hypothesis → Experiment` traversal | **Extend**: add backward-compatible optional fields to templates and build lightweight read-only link/query module (`research.py`) |
| Novelty Ledger | `positioning.py` + `NoveltyLedger.md` + `prompts/positioning.md` / `knowledge-integration.md` with SHA-256 provenance & `inference: true` | Only needs optional cross-links to `Hxx` / `EXP-xxx` IDs and queryable competitor lookup | **Reuse + Extend**: retain validator and workflow; add optional ID links in templates/prompts and read-only indexing |
| 学习路线关联 | `00-Research-Areas/` frontmatter (`research_question`, `contributions`, `novelty_ledger`) | Cannot read external Codex-maintained `research/` files (`RESEARCH_HOME.md`, `EIGHT_WEEK_ROADMAP.md`, `READING_ROADMAP.md`, `RESEARCH_STATE.md`, `IDEA_BOARD.md`, `HYPOTHESIS_REGISTRY.md`, `papers.jsonl`, `weekly/weekXX/PLAN.md`) | **Extend**: add portable `research_dir` / `experiments_dir` config (and auto-detection) + read-only parser in `research.py`, surfaced in `status` & `paperflow research` |
| 实验结果关联 | `Positioning.md` has free-text `## Experimental Use`; `NoveltyLedger.md` has `## Research Decisions and Experiments` | No read-only index across `experiments/reports/*.md` and `research/EXPERIMENT_LEDGER.md` to query by RQ, Hypothesis ID, Citekey, or failure phenomenon | **Extend**: add lightweight read-only index/query (`paperflow find`) without copying or owning experiment data/traces |
| Academic Skills 集成 | `.agents/skills/paperflow/SKILL.md` + `prompts/*.md` + `AGENTS.md` | No routing or boundary definition with `academic-research-suite` (`v3.24.2` in `~/.gemini/config/skills/` and `~/.agents/skills/`), nor 4 natural-language workflow routes | **Extend**: update `SKILL.md`, `AGENTS.md`, `resource-upgrades.json`, and document in `docs/ACADEMIC_SKILLS_INTEGRATION.md` (do not vendor ARS) |
| 检索与知识复用 | `triage._linked_notes`, `process.inspect` resumability, `evidence.jsonl` reuse, `migration.py` | No unified cross-directory search across `01-Literature/` (including `manual-*.md`), `evidence.jsonl`, `03-Synthesis/`, `04-Questions/`, `research/`, and `experiments/` | **Extend**: lightweight in-memory search & reconciliation hints in `research.py` + `paperflow find` (no DB, no vector store) |

---

## 4. Non-Goals Confirmed

Per project rules (`AGENTS.md`) and research workflow boundaries:
- Do **not** replace Zotero as bibliographic/PDF source of truth or write to Zotero.
- Do **not** duplicate bulk PDF downloading or Zotero import workflows (`long_research/scripts/import_zotero_literature.py` owns Stage A).
- Do **not** auto-initialize or overwrite `/home/soren/projects/idea_1117/long_research` or run batch deep reads.
- Do **not** introduce DuckDB, SQLite knowledge graphs, vector DBs, web dashboards, or overlapping agent orchestrators.
- Do **not** vendor `academic-research-skills` into PaperFlow.
