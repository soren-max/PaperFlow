---
paperflow_prompt: paper-synthesis
version: 1
---

# Complete one Literature reading note

Inputs: `paper-map.md`, validated `evidence.jsonl`, `method-card.md`, `result-card.md`, and the existing Literature note for ownership and duplicate checks. Do not reread the full source.

Output: `paper-note.md` with Core Problem, Core Idea, Method, Evidence, Results, Limitations, Research Relevance, and My Questions. Keep it compressed. Every factual point cites at least one `[E001]` style evidence ID. Label research relevance and proposed questions as research inference, not paper findings.

Run `paperflow process <paper>` to validate, then `paperflow process <paper> --publish-note`. Publication inserts a V2 block before `## My Notes`; it preserves Zotero-managed blocks and existing personal notes. Review the resulting Literature note against PDF pages for method, numbers, and limitations.
