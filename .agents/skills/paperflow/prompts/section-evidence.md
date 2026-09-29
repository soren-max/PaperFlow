---
paperflow_prompt: section-evidence
version: 1
---

# Read one section at a time

Inputs: `paper-map.json`, one section's chunk files listed by `paperflow process <paper> --section <id>`, and `structure.json`. Read one chunk, extract cards, then continue with the next chunk. Never load the whole `source.md`.

Output: `evidence/<section-id>.jsonl`, one JSON object per important claim. Required fields: `id` (unique `E001` style), `paper` (exact citekey), `section_id`, `page` (integer PDF page), `type`, `claim`, `evidence_quote`, `source_chunk`, `confidence` (`high`, `medium`, `low`). Valid types: problem, definition, assumption, method, mechanism, dataset, metric, result, ablation, limitation, author_interpretation.

`evidence_quote` must be verbatim from the cited chunk and appear on the cited page. Record table row and column labels with the claim; do not copy a number without its metric, dataset, and setting. A caption is evidence for what a figure/table depicts, not proof of a result hidden in an image. If extraction is garbled, inspect the Zotero PDF and mark the gap for manual review; do not invent a repair. Keep research inference out of these cards.

After writing one section file, run `paperflow process <paper>` to validate it before proceeding.
