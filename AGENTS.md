# PaperFlow research rules

- Product rule: implementation may use a complex internal pipeline, but the personal research interface stays simple. Daily use is `paperflow sync` plus Codex natural-language requests. Keep `triage` optional for batch screening; do not make people run map, extract, cards, or other internal stages.
- `quick`, `normal`, and `deep` are internal processing policy. Infer and apply them from the task and saved state; never require the researcher to choose a level.
- When asked to organize a paper, locate its source and saved artifacts, convert the PDF only when needed, keep reading context bounded, extract reliable conclusions, and update the knowledge base without exposing intermediate commands as required steps.
- Prioritize real research work: reading papers, linking knowledge, comparing methods, finding gaps, forming hypotheses, designing experiments, writing reviews, and simulating peer review.
- Zotero is the bibliographic source of truth.
- `01-Literature/` is source-grounded. Never invent metadata, quotes, findings, or citations, and never silently turn an inference into a paper's claim.
- Put cross-paper reasoning in `02-Concepts/` or `03-Synthesis/`, retaining the source literature citekeys.
- Prefer updating an existing Concept or Synthesis over creating a duplicate.
- Do not modify PaperFlow-managed blocks or `## My Notes` unless explicitly requested.
- Keep Markdown human-readable and mark inference, uncertainty, and missing evidence clearly.
