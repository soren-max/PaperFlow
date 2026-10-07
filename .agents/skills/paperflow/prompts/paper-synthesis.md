---
paperflow_prompt: paper-synthesis
version: 2
---

# Complete one source-grounded Literature reading note

Inputs: paper-map.md, validated evidence.jsonl, method-card.md, result-card.md, and the existing Literature note for ownership and duplicate checks. Do not reread the full source.

Output: paper-note.md with Core Problem, Core Idea, Method, Evidence, Results, Limitations, and Reading Scope. Keep it compressed. Every factual point cites at least one [E001] style evidence ID. For targeted reading, describe only the questions/sections actually covered and mark other results or limitations as unreviewed; do not imply a complete paper read.

Keep contribution overlap, novelty threats, surviving gaps, design implications and researcher hypotheses in the Positioning Card or other Synthesis/Questions. Existing published V2 notes remain unchanged; do not rewrite older blocks just to adopt this format.

Run paperflow process <paper> to validate, then paperflow process <paper> --publish-note. Publication inserts a V2 block before My Notes and preserves Zotero-managed blocks and personal notes. Review method, numbers and limitations against cited PDF pages. When the map declares positioning_path, continue with prompts/positioning.md after paper synthesis/publication.
