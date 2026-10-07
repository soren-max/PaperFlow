---
paperflow_prompt: triage
version: 1
---

# Triage one paper

Inputs: one `packet.md` from `.paperflow/triage/<zotero-key>/`. It contains bounded Literature metadata, abstract, annotations, section titles when ingested, reading and processing status, linked knowledge notes, and brief relevant Research Areas and Questions. It contains no PDF text.

Outputs: `paper-card.md` in the same folder, in exactly this shape:

```markdown
---
paperflow_card: 1
citekey: example2026
zotero_key: ABCD1234
research_area: KG-augmented Retrieval
priority: high
processing_level: deep
basis: abstract, tags
---

# The paper title

## Problem
...

## Method
...

## Dataset
...

## Potential relevance
...

## Basis
...
```

Copy `citekey` and `zotero_key` from the packet; the CLI rejects a card whose keys do not match it. `research_area` names one Research Area from the digest, or a short new label when the paper opens a new area.

Body: `## Problem`, `## Method`, `## Dataset`, `## Potential relevance`, `## Basis`, each under 80 words.

This is a routing decision, not a reading. Write no summary and no narrative of the paper. One or two sentences per section. `## Dataset` may be the single word `unknown`.

`priority` is research value to *this* researcher (`low`, `medium`, `high`), not paper quality or remaining reading effort. Use the brief Research Area content and the actual core of an open Question to judge relevance. Name the specific Area or Question in `## Potential relevance`; linked notes alone do not prove a paper addresses it.

`processing_level` is the depth the paper merits (`triage_only`, `quick`, `normal`, `deep`), independent of priority and completion. Reserve `deep` for a method worth reproducing, results this researcher would cite, a disagreement, or direct relevance to an open Question. The packet's `reading_status` and `processing_status` show what has already been done. If `processed`, state that no repeat deep work is needed; a paper can still have `priority: high` and `processing_level: deep` because that describes its value and warranted depth. Older cards with `deep_processing: "yes"/"no"` remain accepted, but new cards should use `processing_level`.

Set `basis` to the packet inputs the judgment actually rests on, chosen from `abstract`, `title`, `tags`, `annotations`, `venue`, `sections`. Use `sections` only when the packet lists section titles.

Evidence boundary: the abstract, annotations, and metadata are all you have. Do not assert a result, dataset, or claim the packet does not state. Never invent a number, a benchmark, or a limitation. When the packet is too thin to judge — no abstract, no tags, no annotations — say so in `## Basis` and set `deep_processing: no` rather than guessing. Do not read the PDF; that is a later stage and only for papers that earn it.
