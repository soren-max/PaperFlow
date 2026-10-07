# V4: Evidence to positioning to research

V4 adds a question/contribution layer to the existing Markdown workflow. Zotero
still owns bibliography and PDFs; Literature remains source-grounded. The daily
interface is `paperflow sync` and natural-language research requests. No new CLI
command, database, AI runtime, or mandatory batch-triage step is introduced.

## Routing contract

New triage cards use `paperflow_card: 2`, retaining priority, processing_level,
basis and the five bounded body sections. Additional required fields are:

| Field | Values / meaning |
|---|---|
| research_role | direct_competitor, component, baseline, benchmark, mechanism_inspiration, background, survey, archive |
| novelty_threat | low, medium, high, unknown; provisional until reading |
| reading_goal | positioning, implementation, experiment_design, baseline, citation, background |
| target_contributions | Array of saved contribution IDs; empty without an active contribution |
| focus_questions | Array of reading questions; nonempty for targeted |

`processing_level` adds `targeted` to triage_only/quick/normal/deep. It selects
sections needed for a bounded question. The levels remain internal policy; the
researcher does not have to choose one. Archive retains notes and Zotero items.
Priority, novelty threat, role, depth, and completion describe different things.

Version-1 cards remain valid without the new fields. If those fields are present,
they are validated. Legacy deep_processing flags keep their existing mapping and
must agree with processing_level if both are given.

The offline packet includes bounded Research Area contribution mappings,
unresolved Questions, and at most three active `type: novelty-ledger` notes.
Ledger rows are labeled researcher inference. Areas, Questions, and Ledgers have
separate context budgets within the existing 12,000-character digest; the full
packet remains capped at 28,000 characters. Updated research context marks a
previously validated card stale when triage next examines it. Rerouting does not
invalidate a paper's already validated evidence or require a complete reread.

## Question-directed paper maps

The map keeps ordered exact `reading_sections` from structure.json. Optional
fields are processing_level, reading_goal, target_contributions, focus_questions,
and positioning_path. Each focus-question object contains `question` and
`section_ids`; its sections must be selected in reading_sections. If an answer
cannot be located, use an empty section_ids array and explain missing_evidence.
Targeted plans require focus questions. Legacy maps with only reading_sections
remain valid.

For an active project, declare the matching card path, for example
`03-Synthesis/example2026-Positioning.md`. Search existing notes before choosing
the filename. Without an active contribution or research decision, omit the path
and retain ordinary evidence/concept work.

## Positioning Card

Use `90-Templates/Positioning.md` and `prompts/positioning.md`. The card records
what the paper supports, overlap with exact contribution wording, scoped candidate
gaps, design proposals, experimental use, and citation role. It lives inside
03-Synthesis, never Literature or evidence.jsonl.

Required frontmatter for validation: `type: positioning`, exact citekey and
zotero_key, `inference: true`, research_role, novelty_threat, reading_goal,
target_contributions matching the map, source_sha256 matching state.json, and
evidence_sha256 matching the current validated evidence.jsonl bytes. The body
needs an exact Literature link and valid evidence IDs from that paper. Hashes
detect stale provenance; the validator cannot establish semantic correctness,
completeness, or novelty. Cross-paper comparisons still require reading their
actual cited sources.

`process` reconciles positioning_created after paper synthesis. A declared card
that is missing or invalid remains pending, preventing knowledge integration from
being marked complete. Legacy plans skip this stage. Adding a card to an existing
map reuses completed sections, cards, and synthesis. Path checks keep the card
inside 03-Synthesis, including resolved symlinks.

## Project Novelty Ledger and decisions

Use `90-Templates/NoveltyLedger.md` for one ledger per active project. Keep exact
current contribution wording, closest checked work, solved/partial/not-observed/
unknown status, scoped remaining gap, confidence, evidence links, and next
decision. Record checked corpus, date, reading coverage and missing comparisons
under Search Scope. Link exact Literature citekeys and Positioning Cards.

Do not infer global absence from an unread section, absent abstract detail, one
paper, or a limited search. Suggested contribution changes remain proposals next
to the original wording until the researcher adopts them. The ledger is maintained
by Codex in the Vault; PaperFlow does not invent or automatically adjudicate its
claims.

Knowledge integration first checks contribution impact, then updates the matching
ledger, then research-decision Questions and stable Concepts. Without an active
project, it uses the usual Concept/Question workflow. The integration log records
changed files, unchanged ledger judgments and why, proposed revisions, and missing
evidence. Decision Questions define the observation, reading, or experiment that
would settle them.

## Installation and compatibility

Initialization adds missing prompts and templates. Known unmodified shipped
instructions, prompts, skills and affected templates upgrade by LF-normalized
content hashes in resource-upgrades.json. Customized files are preserved byte for
byte. Zotero sync, quote/page evidence checks, the V2 publication block, My Notes,
legacy migration, and completed legacy maps retain their behavior.

Tests cover v1/v2 routing, targeted reading, current claim/ledger context, stale
routing, focus-to-section validation, inference provenance, path confinement,
resumable positioning, preserved Literature, and upgrade/customization behavior.
