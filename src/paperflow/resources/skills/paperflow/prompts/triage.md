---
paperflow_prompt: triage
version: 1
---

# Triage one paper

Inputs: one `packet.md` from `.paperflow/triage/<zotero-key>/`. It contains the Literature frontmatter, parsed metadata, the Zotero abstract, Zotero annotations, section titles when the paper is already ingested, and a digest of the Vault's Research Areas, open Questions, and existing Literature. It contains no PDF text.

Outputs: `paper-card.md` in the same folder, in exactly this shape:

```markdown
---
paperflow_card: 1
citekey: example2026
zotero_key: ABCD1234
research_area: KG-augmented Retrieval
priority: high
deep_processing: "yes"
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

Quote `deep_processing`, because YAML reads a bare `yes` as a boolean.

Copy `citekey` and `zotero_key` from the packet; the CLI rejects a card whose keys do not match it. `research_area` names one Research Area from the digest, or a short new label when the paper opens a new area.

Body: `## Problem`, `## Method`, `## Dataset`, `## Potential relevance`, `## Basis`, each under 80 words.

This is a routing decision, not a reading. Write no summary and no narrative of the paper. One or two sentences per section. `## Dataset` may be the single word `unknown`.

`priority` is relevance to *this* researcher, not paper quality. Derive it from the Research Areas and open Questions in the digest, how much this paper overlaps existing Literature, and whether it fills a gap or duplicates a source already held. Say which in `## Potential relevance`, naming an actual Research Area or Question from the digest.

`deep_processing` is `yes` only when the paper would repay the staged evidence pipeline: a method worth reproducing, results this researcher would cite, a disagreement with an existing source, or direct relevance to an open Question. Reserve `high` + `yes` for a small number of papers.

Set `basis` to the packet inputs the judgment actually rests on, chosen from `abstract`, `title`, `tags`, `annotations`, `venue`, `sections`. Use `sections` only when the packet lists section titles.

Evidence boundary: the abstract, annotations, and metadata are all you have. Do not assert a result, dataset, or claim the packet does not state. Never invent a number, a benchmark, or a limitation. When the packet is too thin to judge — no abstract, no tags, no annotations — say so in `## Basis` and set `deep_processing: no` rather than guessing. Do not read the PDF; that is a later stage and only for papers that earn it.