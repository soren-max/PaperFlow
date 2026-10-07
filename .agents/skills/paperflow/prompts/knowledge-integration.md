---
paperflow_prompt: knowledge-integration
version: 2
---

# Integrate evidence into research decisions

Inputs: final Literature reading note, validated evidence, the Positioning Card when relevant, saved contribution claims, and existing Synthesis, Novelty Ledger, Questions, Concepts and Research Area MOCs. Search titles and aliases before creating anything.

For an active project, prioritize:

1. Check whether the paper strengthens, weakens, narrows, or leaves unchanged each affected contribution claim. Compare the exact claim wording, not just a topic label.
2. Update the existing project Novelty Ledger in `03-Synthesis/` using `90-Templates/NoveltyLedger.md`. Create one only when no matching ledger exists. Link the Positioning Card and exact Literature citekeys. Record already solved / partially / not observed / unknown, the scoped remaining gap, confidence, evidence/reading scope, and proposed next action. Preserve the current claim alongside proposed revisions.
3. Update decision Questions in `04-Questions/`: resolve only when evidence meets the stated resolution criterion; record new uncertainties and the reading or experiment that would settle them.
4. Update stable Concepts only where the evidence warrants it, then Research Area navigation and other relevant Synthesis.

Without an active claim or research decision, retain the usual Concept/Question integration; do not create a speculative ledger. A single-paper positioning note is allowed in Synthesis but must identify its limited basis. Cross-paper conclusions require the papers actually used.

Write `knowledge-integration.md` in the paper artifact folder listing changed files, linked claims/cards/ledger, decisions, proposed contribution changes and unresolved issues. If no ledger row changes, record why. New literature can reopen a resolved decision, but does not justify rereading completed sections without a concrete gap.

Evidence boundary: exact [[citekey]] links for paper claims; explicitly label cross-paper inference, hypotheses and missing evaluation. “Not found” must name the checked corpus/date/reading coverage, never become “does not exist”. Do not modify My Notes or Zotero-managed blocks. Contribution revisions remain proposals unless the user authorizes adopting them.
