# PaperFlow V2 legacy migration strategy

## Ownership and scope

V1 Literature, Concept, Question and Synthesis files are legacy knowledge assets, not disposable generated output. A migration starts from one explicit Zotero key or stable citekey. `paperflow migrate <paper>` captures an immutable baseline under `.paperflow/migrations/<key>/migration.json`; later runs recompute `reconcile.json`. There is no batch command. Zotero owns metadata and original PDFs; `paperflow sync` owns only its marked metadata/annotation blocks. `## My Notes` and existing reasoning notes remain human-owned.

The V2 pipeline writes machine source and intermediate artifacts under `.paperflow/papers/<key>/`. After evidence validation and comparison, `paperflow process <paper> --publish-note` inserts a distinct V2 reading block before `## My Notes`. It refuses to replace a changed V2 block. A Concept, Question or Synthesis edit requires a separate, claim-level decision with evidence IDs; migration never rewrites them automatically.

## State schema

`migration.json` is captured once and never silently refreshed:

```json
{
  "schema_version": 1,
  "captured_at": "UTC timestamp",
  "identity": {
    "zotero_key": "TJFIDLRG",
    "citekey": "zhoundwhat",
    "note_path": "01-Literature/zhoundwhat.md",
    "title": "Zotero-synced title"
  },
  "legacy": {
    "my_notes_sha256": "SHA-256 of the My Notes heading and everything after it",
    "my_notes_characters": 0,
    "v2_present_at_capture": false,
    "assets": [
      {"path": "02-Concepts/Example.md", "kind": "concept", "sha256": "..."}
    ],
    "duplicate_candidates": []
  },
  "manual_review": {
    "decision_file": "migration-review.md",
    "decision": "pending"
  }
}
```

The baseline inventories only Concept, Question and Synthesis Markdown files directly linking the citekey. It stores hashes and paths, not copies of personal text. The V2 `state.json` remains the authority for PDF checksum, converter, source checksum, section progress and stage progress; duplicating that state in `migration.json` would create two writable authorities.

`reconcile.json` is replaceable derived state: `status`, `checked_at`, `pipeline_stages`, `my_notes_preserved`, changed and newly linked legacy asset paths, current duplicate candidates, `manual_review_decision`, and `issues`. The authored `migration-review.md` holds the claim-by-claim comparison and any source conflicts. Its standalone `Decision: pending|accepted|rejected` line is the human gate. `migrated` requires a validated published V2 note, recorded knowledge review, no drift/provenance issues, and `Decision: accepted`. A duplicate candidate remains visible for review; it is never automatically merged or deleted.

## Reconcile rules

| Check | Result |
| --- | --- |
| Same Zotero key, citekey, Literature path and title | Any identity mismatch is `conflict`; a Zotero metadata correction may change the managed block without changing `My Notes`. |
| `## My Notes` heading and following content hash unchanged | A mismatch or missing unique boundary is `conflict`. V2 publication must not change this region. |
| Previously linked Concept/Question/Synthesis hashes unchanged | Drift or a newly linked file is `conflict` for review, not an instruction to revert human work. |
| V2 PDF locator exists and matches its ingested checksum; source/chunks pass integrity checks | Missing/changed source or invalid evidence is `conflict`. Re-ingestion needs an explicit new provenance decision. |
| Paper map, per-section evidence, cards, synthesis, Literature block and knowledge review validate | Until the stages are complete, `pipeline_pending`; afterward, `review_required`. Resume from the first pending section or stage. |
| Manual claim audit accepted with no issues | `migrated`. An explicit rejected decision becomes `rejected`; a separate human workflow decides revision or retirement. |

This is an audit protocol, not a semantic claim matcher. Quote/page validation proves location, while the human audit decides whether the old and new claims mean the same thing, whether a table header was interpreted correctly, and which research inferences remain useful. A baseline captured after V2 publication records that fact and cannot prove preservation of the earlier period.

## Two-paper validation, 2026-09-18

| Sample | Legacy → V2 delta | Reconcile result |
| --- | --- | --- |
| `zhoundwhat` / BRINK, `TJFIDLRG` | Existing research-rich `## My Notes` retained with the same content hash after universal-newline decoding. New 17-page source, 51 chunks, 20-section map, 46 evidence cards, method/result cards and compressed V2 Literature block. Existing linked Concept/Question files unchanged; no Synthesis link. | `review_required`; both `My Notes` and linked-asset hashes match the baseline. |
| `jiangndkg` / KG-Agent, `J68KBEZ6` | Existing V2 processing reused: 19-page source, 32 chunks, 15-section map, 37 evidence cards and Literature block. Legacy `## My Notes` and linked Concept/Question files unchanged since this migration baseline. | `review_required`; baseline was captured after V2 publication, so historical pre-publication preservation is not claimed. |

BRINK has a second Zotero item, `YURUBABL`, whose PDF has the same SHA-256 as `TJFIDLRG`. Existing knowledge links point to `[[zhoundwhat]]`; this run used that citekey and did not alter the duplicate. Its Zotero year is empty although the PDF cover prints EACL 2026. KG-Agent's Zotero year/DOI are also empty. Metadata questions belong in Zotero. The per-paper migration reviews record supported claims, qualified interpretations, deferred details and source conflicts.

## Migration sequence for another paper

1. Run `paperflow migrate <citekey>` before changing its Literature note. Check duplicate candidates and record the baseline location.
2. Run `paperflow ingest <citekey>`, then build the paper map and read selected sections one bounded chunk at a time. Validate each evidence file with `paperflow process`.
3. Build method/result cards and a concise `paper-note.md`. Compare every important old factual claim with evidence IDs; preserve unsupported or uncertain statements in `## My Notes` pending review.
4. Write `migration-review.md` with differences and human questions. Publish the validated V2 block, then rerun `paperflow migrate <citekey>` and confirm hashes.
5. Review linked Concepts, Questions and Synthesis individually. Record deliberate edits and their evidence; leave the audit decision pending until a human accepts the comparison.
