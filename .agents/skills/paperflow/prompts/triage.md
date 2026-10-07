---
paperflow_prompt: triage
version: 2
---

# Route one paper around current research

Inputs: one bounded `packet.md` from `.paperflow/triage/<zotero-key>/`. It contains Literature metadata, abstract, annotations, available section titles, reading/processing status, relevant Research Areas, open Questions, and active Novelty Ledgers. Ledgers are researcher interpretation, not paper evidence. No PDF text is included.

Output: `paper-card.md` beside the packet:

```markdown
---
paperflow_card: 2
citekey: example2026
zotero_key: ABCD1234
research_area: Example research area
priority: high
processing_level: deep
research_role: direct_competitor
novelty_threat: unknown
reading_goal: positioning
target_contributions: []
focus_questions:
  - Which parts of the active claim does this method implement?
basis: abstract, tags
---

# The paper title

## Problem
...

## Method
...

## Dataset
unknown

## Potential relevance
...

## Basis
...
```

Copy citekey and Zotero key exactly. `research_area` names a saved Area or a short new label. Each body section is at most 80 words; write one or two sentences rather than a paper summary.

`priority` (`low`, `medium`, `high`) is research value, independent of reading effort or completion. In Potential relevance name an active contribution or decision Question and explain the provisional relationship. Use saved contribution IDs in `target_contributions`; use `[]` when no contribution is active. Do not invent the researcher's claims from a paper's abstract.

`research_role`: `direct_competitor`, `component`, `baseline`, `benchmark`, `mechanism_inspiration`, `background`, `survey`, `archive`. Choose the primary role for the current project. Archive retains the synced note; it does not delete Zotero items or Vault files.

`novelty_threat`: `low`, `medium`, `high`, `unknown`. This is a provisional routing judgment, never a verified novelty conclusion. A benchmark can be high priority with low threat. Use unknown when evidence or an active claim is absent. Explain high threat as a suspected overlap that reading must test.

`reading_goal`: `positioning`, `implementation`, `experiment_design`, `baseline`, `citation`, `background`. `focus_questions` is an array of concrete questions that the reading should answer, derived from saved claims and open decision Questions. Empty is valid except for targeted reading.

Infer `processing_level` internally:

- `triage_only`: archive or insufficient source context.
- `quick`: skim for relevance or a citation.
- `targeted`: answer bounded mechanism, competitive, or experimental questions by selecting specific sections; include nonempty focus_questions.
- `normal`: a broader method/result reference read.
- `deep`: competitive comparison or reproduction requiring extensive evidence.

The researcher need not choose a level. Deep Competitive Read, Targeted Mechanism Read, Experimental Reference Read, Skim, and Archive are useful descriptions, not additional mandatory fields. The packet's reading and processing statuses indicate completed work: reuse existing evidence and never recommend repeating a complete read solely because priority or threat is high. A new question may warrant only the missing sections.

Set `basis` only to packet source inputs actually used: `abstract`, `title`, `tags`, `annotations`, `venue`, `sections`. Sections requires available headings. Research context steers relevance but cannot establish a paper's mechanism, result, limitation, or absence of a feature. Record unsupported/unknown instead of guessing. With thin metadata choose triage_only and explain the gap. Never open the PDF during triage.

Old version-1 cards and legacy deep_processing flags remain accepted; new cards use version 2 and processing_level.
