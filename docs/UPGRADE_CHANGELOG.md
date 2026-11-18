# PaperFlow Upgrade Changelog (Research Workflow Adaptation)

> Branch: `feat/academic-workflow-upgrade` (from `v0.1.4` `ba0760d`)

## Summary of Changes

### 1. Zotero Read-Only Local API Fallback & Windows/WSL Path Portability
- `src/paperflow/zotero.py`:
  - Preserved `zotero-agent` bridge (`_run_zot`) as primary path when configured/available.
  - Added strictly read-only Zotero Local HTTP API (`http://127.0.0.1:23119/api/users/0/...`) fallback (`zotero_backend = "auto" | "bridge" | "local_api"`), supporting `ping`, `list_collections`, recursive/deduplicated `fetch_snapshot`, annotations, `Citation Key:` extraction from `extra`, and `fetch_paper_pdf` (`file/view/url`).
  - Added `zotero_context(config)` using `contextvars` so CLI commands configure the backend without breaking single-argument mock signatures.
- `src/paperflow/config.py`:
  - Added `normalize_local_path()` and `resolve_vault_relative_path()` for `file://`, Windows drive paths (`C:\...`), and WSL UNC paths (`\\wsl.localhost\...`).
  - Added optional `Config` fields (`research_dir`, `experiments_dir`, `zotero_backend`, `zotero_local_api_url`) with auto-detection for `<vault>/research` and `<vault>/experiments` and full backward compatibility with V1–V4 `config.toml`.
- `src/paperflow/ingest.py` & `src/paperflow/migration.py`:
  - Resolved PDF attachment locators through `normalize_local_path()` so Windows Zotero storage paths work seamlessly when running PaperFlow inside WSL.
  - Added `PackageNotFoundError` fallback for converter version metadata in mocked environments.
- `src/paperflow/discovery.py`:
  - Extended `discover_vaults()` and `zotero_profile_found()` to inspect WSL-mounted Windows `AppData/Roaming` locations alongside native `%APPDATA%` and `.paperflow` roots.

### 2. Read-Only 8-Week Research Program Integration & Traceability (`P0` + `P1`)
- `src/paperflow/research.py` *(new)*:
  - Read-only parsers for `RESEARCH_HOME.md`, `RESEARCH_STATE.md`, `READING_ROADMAP.md`, `HYPOTHESIS_REGISTRY.md`, `IDEA_BOARD.md`, `EXPERIMENT_LEDGER.md`, `papers.jsonl`, `weekly/weekXX/PLAN.md`, and `experiments/reports/*.md`.
  - Manual note reconciliation (`detect_manual_notes()`) matching `01-Literature/manual-*.md` notes against `manifest.json` and `papers.jsonl` by Zotero item key or DOI.
  - Bounded `render_research_digest()` hooked into `src/paperflow/triage.py` (`context_digest`) only when a linked research/experiments directory exists.
  - Lightweight in-memory `build_research_index()` and `query_research()` supporting queries by paper citekey/Zotero key, `RQ-xx`, `Hxx`, `EXP-xxx`, `competitor`, or `evidence`/failure keywords without adding any DB or vector store.
- `src/paperflow/positioning.py`:
  - Validated optional `rq_ids`, `hypothesis_ids`, `experiment_ids`, `baseline_for`, and `challenged_by_experiments` frontmatter lists while keeping existing Positioning Cards 100% compatible.
- `src/paperflow/cli.py`:
  - Added compact `Research` row to `paperflow status` when a research program is linked; enhanced `paperflow doctor` with Zotero backend mode and optional `research_dir` / `experiments_dir` checks.
  - Preserved new `Config` fields across `paperflow init`.
  - Added read-only commands `paperflow research` and `paperflow find`.

### 3. Academic Skills Routing & Optional Mentor Reading Template (`P0` + `P2`)
- `src/paperflow/resources/templates/MentorReading.md` *(new)* & `VAULT_RESOURCES` in `cli.py`:
  - Optional 8-section first-year graduate study template separating `[E001]` paper facts from labeled teaching explanations and reflection questions.
- `src/paperflow/resources/templates/{Positioning,NoveltyLedger,Question}.md`:
  - Added optional `rq_ids`, `hypothesis_ids`, `experiment_ids` (plus `baseline_for`, `challenged_by_experiments` on `Positioning.md`).
- `.agents/skills/paperflow/SKILL.md`, `src/paperflow/resources/AGENTS.md`, `prompts/positioning.md`, `prompts/knowledge-integration.md`:
  - Added division-of-labor routing with `academic-research-suite` (`v3.24.2`) and read-only rules for external `research/` and `experiments/`.
- `src/paperflow/resources/resource-upgrades.json`:
  - Registered `0.1.4` LF-normalized SHA-256 hashes so unmodified V4 Vaults upgrade cleanly while customized files remain untouched.

### 4. Documentation & Tests
- Added `docs/ACADEMIC_WORKFLOW_AUDIT.md`, `docs/ACADEMIC_SKILLS_INTEGRATION.md`, `docs/LONG_RESEARCH_INTEGRATION.md`, `docs/UPGRADE_CHANGELOG.md`, `docs/examples/long_research.config.toml`.
- Added `tests/test_academic_workflow.py` covering portable path normalization, V1/V4 config compatibility, Zotero Local API fallback (collections, items, annotations, PDF URI), `ingest` & `migration` URI handling, bidirectional `Paper ↔ RQ ↔ Hypothesis ↔ Experiment` queries, `triage` context digest integration, `init` resource preservation, and graceful offline degradation.
