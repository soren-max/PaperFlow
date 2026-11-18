# PaperFlow research rules

- Product rule: implementation may use a complex internal pipeline, but the personal research interface stays simple. Daily use is `paperflow sync` plus Codex natural-language requests. Keep `triage` optional for batch screening; do not make people run map, extract, cards, or other internal stages.
- `quick`, `targeted`, `normal`, and `deep` are internal processing policy. Infer and apply them from the task and saved state; never require the researcher to choose a level.
- When asked to organize a paper, locate its source and saved artifacts, convert the PDF only when needed, keep reading context bounded, extract reliable conclusions, and update the knowledge base without exposing intermediate commands as required steps.
- Prioritize real research work: reading papers, linking knowledge, comparing methods, finding gaps, forming hypotheses, designing experiments, writing reviews, and simulating peer review.
- Zotero is the bibliographic source of truth.
- `00-Research-Areas/` names what this researcher is actually working on. Keep it current: optional batch triage reads it together with `04-Questions/` to judge relevance and internal processing depth.
- `01-Literature/` is source-grounded. Never invent metadata, quotes, findings, or citations, and never silently turn an inference into a paper's claim.
- Put cross-paper reasoning in `02-Concepts/` or `03-Synthesis/`, retaining the source literature citekeys.
- For an active project, read saved contribution claims and research-decision Questions before routing papers. Keep Positioning Cards and a project Novelty Ledger in `03-Synthesis/`; update positioning and decisions before stable Concepts.
- Treat novelty threat as provisional. Distinguish explicit paper limitations from features not observed in reviewed sections; retain checked corpus, date, and evidence coverage for negative conclusions.
- Prefer updating an existing Concept or Synthesis over creating a duplicate.
- When an external research program (`research/` roadmap, `HYPOTHESIS_REGISTRY.md`, `EXPERIMENT_LEDGER.md`) or `experiments/` directory is linked, treat it as read-only reference context unless explicitly asked to update progress; use `RQ-xx`, `Hxx`, `EXP-xxx`, and `[[citekey]]` links to trace `Paper → RQ → Hypothesis → Experiment`.
- Coordinate with `academic-research-suite` without duplicating it: PaperFlow owns Zotero sync, local PDF evidence extraction, citation provenance, Positioning Cards, and Novelty Ledgers; `academic-research-suite` owns external discovery, research-question framing, experimental design, and paper writing/reviewing.
- Do not modify PaperFlow-managed blocks or `## My Notes` unless explicitly requested.
- Keep Markdown human-readable and mark inference, uncertainty, and missing evidence clearly.
