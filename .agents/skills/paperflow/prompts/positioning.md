---
paperflow_prompt: positioning
version: 1
---

# Position a paper against active contribution claims

Inputs: validated evidence.jsonl, paper map, method/result cards, paper-note.md, current contribution claims, relevant Questions and existing Positioning/Synthesis/Novelty Ledger notes. Reuse saved evidence; inspect further bounded sections only to resolve a specific missing answer.

Output: a Positioning Card at the map's positioning_path inside `03-Synthesis/`, using `90-Templates/Positioning.md`. This is researcher inference and must never be published into Literature, evidence.jsonl, or My Notes. Search and update a matching card rather than create a duplicate. Copy the exact citekey, Zotero key and source_sha256 from state; set evidence_sha256 to the SHA-256 of current validated evidence.jsonl bytes. Copy target_contributions from the map. These fields let process detect a card based on obsolete evidence; they do not establish the truth of its interpretation.

Write only sections that help the research decision:

- Role and reading scope: primary role, goal, reviewed sections/pages, unreviewed material, confidence.
- What it already solves: supported capabilities, with exact [[citekey]] links and [E001] evidence IDs from this paper.
- Overlap with active contributions: compare the precise saved claim against those capabilities; label the comparison as inference.
- Unverified or unsupported capabilities: distinguish an explicit author limitation, a feature not observed in reviewed sections, and a still-unread answer. Partial reading cannot prove absence.
- Strongest novelty threat: which part of the contribution needs narrower wording, with evidence and uncertainty.
- Surviving gap: a scoped candidate gap, not a declaration that no prior work exists.
- Implication for design: proposed changes, alternatives and what would test them. Keep original and proposed claim wording separate; do not silently rewrite the researcher's contribution.
- Experimental use and citation role: potential baseline, benchmark, mechanism transfer, or differentiation paragraph, with support.
- Open decisions and sources: exact citekeys, evidence IDs, artifact location, and reading/search coverage.

For negative conclusions use “not observed in the reviewed sections” or “not found in the checked corpus as of <date>”. Record the corpus and scope. A missing feature in one paper, high triage threat, or one mechanism inspiration cannot establish global novelty.

After validation, knowledge-integration.md updates the project's Novelty Ledger and decision Questions before stable Concepts. A Positioning Card may concern a single paper; a global Ledger accumulates comparisons across the project.
