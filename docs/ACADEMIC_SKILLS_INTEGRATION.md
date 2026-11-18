# Academic Research Skills × PaperFlow Integration Design

> Verified on local machine: 2026-11-18  
> Target runtimes: Gemini CLI / Antigravity (`~/.gemini/config/skills/`) and Codex (`~/.agents/skills/`, Vault `.agents/skills/`)

## 1. Local Skill Inventory Verification

Actual filesystem inspection on this WSL host established which versions are installed and active:

| Location | Target / Version | Role | Active in |
|---|---|---|---|
| `/home/soren/.gemini/config/skills/academic-research-suite` | Symlink → `/home/soren/projects/skillpack/academic-research-skills-codex/skills/academic-research-suite` (`v3.24.2`, commit `71528d9`) | Primary academic research suite (`SKILL.md` router + `ars/<workflow>/WORKFLOW.md`) | Gemini CLI / Antigravity (via `/home/soren/.gemini/config/skills.json`) |
| `/home/soren/.agents/skills/academic-research-suite` | Symlink → same `academic-research-skills-codex/skills/academic-research-suite` (`v3.24.2`) | Same suite, shared cleanly without duplicate copies | Codex CLI (WSL) |
| `/home/soren/.gemini/config/skills/skillpack-router` | Symlink → `/home/soren/projects/skillpack/management/skills/skillpack-router` | Selects smallest sufficient skill set across research, slides, and figures | Gemini CLI & Codex CLI |
| `/home/soren/projects/skillpack/academic-research-skills` | `Imbad0202/academic-research-skills` (commit `cfd081d`) | Upstream Claude Code source checkout (inactive reference only; not linked into `~/.gemini/config/skills` or `~/.agents/skills`) | Inactive reference |
| `panshaowu/academic-research-skills` | Not installed locally | Referenced as an external Gemini adaptation pattern only | Not present |
| `/home/soren/projects/PaperFlow/.agents/skills/paperflow` | Workspace skill (`SKILL.md` + `prompts/*.md`) | PaperFlow Zotero/PDF/Vault skill; installed into Vaults by `paperflow init` | PaperFlow repo & initialized Vaults |

### Important Gemini CLI vs Claude Code / Codex Differences
1. **Discovery Paths**: Gemini CLI/Antigravity reads configured directories in `~/.gemini/config/skills.json` (`/home/soren/.gemini/config/skills/`) plus workspace `.agents/skills/` (when opened in PaperFlow or a `paperflow init`-prepared Vault). Codex reads `~/.agents/skills/` plus project `.agents/skills/`.
2. **Entry Convention (`SKILL.md` vs `WORKFLOW.md`)**: `academic-research-suite` uses a single root `SKILL.md` router and names internal workflows `ars/<workflow>/WORKFLOW.md` (`deep-research`, `academic-paper`, `academic-paper-reviewer`, `academic-pipeline`, `sr-screener`, `experiment-agent`) so the agent runtime does not register six overlapping top-level skills.
3. **Tool Mapping**: Upstream Claude-specific constructs (`Skill` tool, `${CLAUDE_PLUGIN_ROOT}`, `AskUserQuestion`, Claude `hooks/hooks.json`) do not execute in Gemini CLI or Codex; `academic-research-suite/SKILL.md` already translates them to native file reads, web browsing/search, and package-relative paths under `ars/`.
4. **No Duplication**: PaperFlow does **not** copy `academic-research-suite` into `.agents/skills/paperflow/`. Both remain independent skills coordinated by lightweight routing rules in `SKILL.md` and `AGENTS.md`.

---

## 2. Role & Responsibility Boundary

| System | Owns | Never Owns / Never Overwrites |
|---|---|---|
| **PaperFlow** (`paperflow` CLI + `.agents/skills/paperflow`) | Zotero read-only sync (`01-Literature/`), `manifest.json`, optional batch `triage`, PDF `ingest` & bounded section reads, quote/page-validated `evidence.jsonl`, V2 Literature note publication (`<!-- paperflow:v2 -->`), per-paper Positioning Cards & project Novelty Ledgers (`03-Synthesis/`), `Paper ↔ RQ ↔ Hypothesis ↔ Experiment` read-only indexing (`paperflow find`) | Zotero database writes, bulk PDF downloading, external `research/` roadmaps/ledgers, raw experiment traces, external literature search reports |
| **Academic Research Skills** (`academic-research-suite`) | External literature discovery (`deep-research` `lit-review` / `three-way-scan`), RQ refinement (`socratic` / `research_question_agent`), gap & hypothesis framing, experimental design & statistical validation (`experiment-agent` `plan` / `validate`), academic paper drafting (`academic-paper`) & peer review simulation (`academic-paper-reviewer`) | Local Zotero database state, PaperFlow manifest/managed blocks, personal `## My Notes` |
| **Codex (8-Week Mentor)** | Weekly study guidance, `research/RESEARCH_HOME.md`, `EIGHT_WEEK_ROADMAP.md`, `READING_ROADMAP.md`, `RESEARCH_STATE.md`, `IDEA_BOARD.md`, `HYPOTHESIS_REGISTRY.md`, `EXPERIMENT_LEDGER.md`, `weekly/weekXX/`, and `experiments/` execution | Overwriting PaperFlow-managed metadata/annotation/V2 blocks or fabricating paper quotes without PaperFlow evidence |

---

## 3. Minimal Routing Protocol (4 Core Research Scenarios)

These rules are encoded concisely in `.agents/skills/paperflow/SKILL.md` and `AGENTS.md`:

| User Request Pattern | Primary Skill(s) | Step-by-Step Division of Labor |
|---|---|---|
| **1. “精读这篇论文” / Organize or deep-read a paper** | **PaperFlow** (optional **MentorReading** template / ARS `three-way-scan` only for framing) | 1. PaperFlow locates the Zotero item / `manifest.json` entry / `manual-*.md` card.<br>2. If needed, ingest PDF once and read bounded section chunks (`paperflow process`).<br>3. Validate exact page/quote evidence (`evidence.jsonl`), cards, and `paper-note.md`, then publish before `## My Notes`.<br>4. If requested in mentor mode, populate `90-Templates/MentorReading.md` keeping verified `[E001]` facts separate from teaching notes and student questions. |
| **2. “它和我的研究 Idea 有什么关系” / Position paper against ideas & hypotheses** | **PaperFlow** (evidence + state) → **academic-research-suite** (`deep-research` synthesis / RQ framing) → **PaperFlow** (Positioning & Ledger persistence) | 1. PaperFlow supplies verified `evidence.jsonl`, existing Positioning Cards, Novelty Ledger, and matching `RQ-xx` / `Hxx` links from `research/`.<br>2. `academic-research-suite` analyzes conceptual overlap, novelty threats, alternative explanations, and candidate design refinements.<br>3. PaperFlow persists the Positioning Card (`inference: true`, `source_sha256`, `evidence_sha256`) and updates the project Novelty Ledger / `04-Questions/` without altering `01-Literature/` evidence or overwriting Codex's `research/` files. |
| **3. “实验发现一个新现象，请寻找相关工作” / Phenomenon-driven search** | **PaperFlow** (`paperflow find` local corpus check) + **academic-research-suite** (`deep-research` `three-way-scan` / `lit-review`) | 1. Run `paperflow find "<phenomenon or Hxx>"` first to check already-synced Literature, validated `evidence.jsonl`, `manual-*` cards, and `EXPERIMENT_LEDGER.md` / `experiments/reports/`.<br>2. Delegate external literature search & source verification to `academic-research-suite` (`ars/deep-research/WORKFLOW.md`).<br>3. Keep external candidates in search logs / `04-Questions/` or `03-Synthesis/` until the researcher imports selected papers into Zotero and syncs them into PaperFlow. |
| **4. “更新本周读论文进度” / Update weekly reading progress** | **PaperFlow** (read state check) + **Codex/Workspace weekly notes** (status update only) | 1. Inspect PaperFlow `reading_status` / `processing_status` (`paperflow status` or `paperflow research`) and existing `01-Literature/` / `weekly/weekXX/` state.<br>2. Update only reading status, weekly checklist/notes, and links (`[[citekey]]`, `RQ-xx`, `Hxx`).<br>3. **Do not** re-ingest PDFs or regenerate already validated paper analyses. |

---

## 4. Guardrails Against Duplication & Drift

1. **No Vendoring**: `academic-research-suite` stays in `/home/soren/projects/skillpack/academic-research-skills-codex` and is linked once at `~/.gemini/config/skills/` and `~/.agents/skills/`.
2. **No Automatic Vault Activation in `long_research`**: When working inside a project before `paperflow init` is run, PaperFlow commands can read `.paperflow/config.toml` if present, or be configured later per paper; PaperFlow never alters `research/` or `experiments/` files unprompted.
3. **Source Grounding**: Claims coming from `academic-research-suite` web searches or `experiments/reports/` must retain their exact provenance tag (`published paper`, `preprint`, `experiment run ID`, `researcher inference`) and never enter PaperFlow `evidence.jsonl` or `<!-- paperflow:begin metadata -->` blocks.
