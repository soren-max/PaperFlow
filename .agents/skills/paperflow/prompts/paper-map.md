---
paperflow_prompt: paper-map
version: 2
---

# Map research questions to bounded paper sections

Inputs: `state.json`, `structure.json`, saved triage card when present, active contribution claims and relevant decision Questions. Read only bounded chunks containing title, abstract, headings, captions, conclusion, and limitations. Do not load `source.md` in full. Triage is optional: infer the goal and questions from the request and saved research context when no card exists.

Outputs: `paper-map.md` with Problem, Method sections, Experiment sections, Important tables/figures, Limitations, Focus questions, and Reading plan. Separate the author's stated problem from the researcher's angle. For each focus question map the needed exact section IDs, the evidence sought, and any unlocated answer. Include sections needed to check counterevidence, qualifications, and experimental settings, not just supporting claims.

Write `paper-map.json` with ordered `reading_sections`. For research-directed work use:

```json
{
  "processing_level": "targeted",
  "reading_goal": "positioning",
  "target_contributions": ["saved_contribution_id"],
  "focus_questions": [
    {"question": "What does the objective optimize?", "section_ids": ["exact-id-from-structure"]},
    {"question": "Is future state predicted?", "section_ids": [], "missing_evidence": "No relevant section located yet; absence is unverified."}
  ],
  "reading_sections": ["exact-id-from-structure"],
  "positioning_path": "03-Synthesis/example2026-Positioning.md"
}
```

Every question's section_ids must be selected in reading_sections. An empty section list requires a missing_evidence explanation. Targeted reads need focus_questions; stop when the bounded questions have sufficient evidence, and record unanswered ones explicitly. Old maps containing only reading_sections remain valid.

Set positioning_path when an active research claim or decision question makes positioning useful. Search existing Synthesis by citekey, title, aliases, and project before choosing a path; reuse a matching card. It must be a Markdown path inside 03-Synthesis. If there is no active project, omit positioning_path and do the ordinary evidence workflow. Existing completed reads can gain a positioning_path without rereading already validated sections.

Evidence boundary: this is a plan, not a summary. Flag unreadable captions; do not assert results before reading their sections/tables, or infer that a feature is absent from headings. Keep the chain research question → reading question → section → evidence visible.
