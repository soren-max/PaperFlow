---
paperflow_prompt: legacy-migration
version: 1
---

# Migrate one existing paper

Inputs: the synced citekey, its current Literature note, `.paperflow/migrations/<key>/migration.json`, existing linked Concept/Question/Synthesis notes, and the V2 paper artifacts. Run `paperflow migrate <citekey>` before editing the Literature note. Do not capture a new baseline if one exists.

Write `migration-review.md` with a standalone `Decision: pending` line and a claim-by-claim table: old claim, V2 evidence IDs and PDF pages, decision to retain/qualify/defer, and uncertainty. Separate reported findings, author interpretations, researcher calculations and research hypotheses. Record duplicate Zotero items, metadata discrepancies and conversion defects for human review. Keep `## My Notes` and existing reasoning notes unchanged. Publish the V2 block only after staged evidence and cards validate, then rerun `paperflow migrate <citekey>` and inspect `reconcile.json`.

Do not mark `Decision: accepted` on behalf of the user. No batch migration, automatic Concept/Synthesis rewrite, Zotero metadata repair or duplicate deletion.
