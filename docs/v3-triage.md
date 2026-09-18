# PaperFlow V3 triage

Status: implemented 2026-09-18 · skill pass on the real Vault not yet run

## Why triage exists

V2 gave every synced paper the same path: `ingest` the PDF, convert it, read it section by section, extract evidence cards. That path is worth its cost for a paper the researcher will actually cite, and wasteful for the rest. With a Zotero backlog, V2 offers no way to choose.

V3 adds the cheap first pass. `paperflow triage` decides whether a paper deserves the V2 pipeline; only a card that says `deep_processing: "yes"` continues.

The design constraint is that triage must be far cheaper than what it gates. It never reads the PDF, and it adds no Zotero round trip: the synced Literature note already holds the source-grounded metadata, abstract, and annotations, so triage is a pure-filesystem operation with no converter dependency and no bridge requirement.

## Division of work

PaperFlow keeps its existing split: the CLI owns deterministic facts and validation, the Codex skill owns reasoning, and the CLI never calls a model.

```text
01-Literature/<citekey>.md + .paperflow/papers/<key>/structure.json (if ingested)
  -> paperflow triage           builds .paperflow/triage/<key>/packet.md
  -> Codex + prompts/triage.md  writes .paperflow/triage/<key>/paper-card.md
  -> paperflow triage           validates the card, records state.json, prints priorities
```

Repeated runs order still-pending papers first, so a large backlog is walked in batches of `--limit` (default 25). A paper re-enters the queue when its note changes, detected by comparing the stored note hash against the current note — the same recompute-from-durable-files approach `paperflow process` uses.

## Packet contract

`packet.md` carries, in order: provenance (`citekey`, `zotero_key`, note path), the note's YAML frontmatter verbatim, parsed metadata, the abstract, the Zotero annotations, section titles when `structure.json` exists, and a digest of the Vault's research context. It closes with a reading boundary that states no PDF text is present.

Budgets are fixed constants in `src/paperflow/triage.py`: abstract 4,000 characters, context digest 20,000 characters or 300 entries, with an explicit omission marker when either is reached. The context digest lists `00-Research-Areas/` and `04-Questions/` notes by title and tags, then existing Literature by citekey, title, and tags — this is what `Potential relevance` is judged against, which is why `00-Research-Areas/` is now created by `paperflow init`.

## Card contract

Machine-readable fields live in frontmatter so the CLI parses them deterministically instead of reading prose:

```markdown
---
paperflow_card: 1
citekey: jiangndkg
zotero_key: J68KBEZ6
research_area: KG-augmented RAG
priority: high
deep_processing: "yes"
basis: abstract, tags
---
```

Body sections `## Problem`, `## Method`, `## Dataset`, `## Potential relevance`, and `## Basis` are each capped at 80 words. There is deliberately no summary section: a card is a routing decision, and the word cap is what enforces that rather than merely asking for it.

`paperflow triage` rejects a card that:

- has no frontmatter, or lacks `paperflow_card: 1` or any required field;
- has a `citekey` or `zotero_key` that does not match the packet's state, which catches a card written for the wrong paper;
- uses a `priority` outside `low`/`medium`/`high` or a `deep_processing` outside `yes`/`no`;
- omits a body section, leaves one empty, or exceeds the 80-word cap;
- names a `basis` entry outside `abstract`, `title`, `tags`, `annotations`, `venue`, `sections`;
- cites `sections` as a basis when the packet contained no section titles.

`basis` is the evidence boundary in miniature: a triage judgment has to say which packet inputs it rests on, and the last rule stops a card claiming section-level reading of a paper that was never ingested.

YAML reads a bare `yes` as a boolean, so the prompt shows `deep_processing: "yes"` quoted and the validator normalizes booleans either way.

## Measured result

`paperflow triage` was run on the real Vault (`E:\Obsidian\Research`, 3 synced items) and prepared three packets. Packet size against the ingested source for the two papers that have one:

| Paper | Packet | `source.md` | Ratio |
| --- | ---: | ---: | ---: |
| KG-Agent (`J68KBEZ6`) | 5,676 chars | 79,937 chars | 7.1% |
| What Breaks KG-based RAG? (`TJFIDLRG`) | 7,318 chars | 71,751 chars | 10.2% |
| Third item (`YURUBABL`, not ingested) | 4,139 chars | — | — |

The comparison is between the triage packet and the converted full text, measured on two papers. It shows the packet is roughly an order of magnitude smaller than the source; it is **not** a measured end-to-end token saving, because the prompt and the vault context the skill reads also cost tokens.

This was the first run against the real Vault. It already carried 17 `00-Research-Areas/` notes and 4 open `04-Questions/` notes, and the digest picked them up — including `Incomplete KG`, `Adaptive GraphRAG`, `Dynamic Routing`, and four questions about how missing KG types affect GraphRAG, which is precisely what both ingested papers are about. The relevance signal is therefore exercised on real material, not only on fixtures.

The KG-Agent note has no Zotero tags and no venue, so its card can rest only on the abstract — the expected outcome for a thin Zotero record, and the case `prompts/triage.md` tells the skill to mark rather than guess.

## Not yet measured

The reasoning half has not run on the real Vault: no `paper-card.md` exists yet, because that pass needs Codex. The CLI half is covered by `tests/test_triage.py` (22 tests) including packet contents, digest truncation, backlog ordering and staleness, every rejection rule above, and the command's exit codes.

Still to do, in the order that matters:

1. Run the skill over the three prepared packets and confirm the cards validate.
2. Compare the triage calls against a full V2 read of the same two papers — do `priority` and `deep_processing` agree with what a deep read concludes? That is the acceptance question from the V3 plan, and it needs both passes on the same paper.
3. Check the word cap and the 80-word sections in practice. If good cards routinely need more, the cap is wrong and should move; if they fit, the cap is doing real work.
4. Broaden past three papers. Triage quality on a backlog of 50 is a different question from triage quality on three.

## Known limits

Relevance is only as good as `00-Research-Areas/`. On a Vault where that folder is empty or stale, every card's `Potential relevance` is weak, and the CLI cannot detect that — it can only report an empty digest. Nothing in the pipeline updates those notes automatically; that still needs a human.

The section-title list is the converter's heading list, unfiltered. The KG-Agent packet's 51 entries include front-matter duplicates, `Algorithm 1`/`Algorithm 2` pseudo-headings, and `<mark>` prompt-template fragments from Appendix D. It is signal and noise together. A deterministic filter would risk dropping a real section, so the packet passes the list through and the prompt tells the skill to read it as structure, never as content. If this proves expensive on a large backlog, filtering belongs in the ingest stage that already owns section detection — not in triage.

Triage reads the Literature note, so it inherits `sync`'s state. A paper that exists in Zotero but was never synced cannot be triaged, and an abstract missing in Zotero is missing here. The packet says `unavailable` rather than inventing one.

The CLI validates structure, provenance, and the evidence boundary. It cannot check whether a `priority` judgment is any good. That is what the comparison in step 2 is for.

## Next phase

Per the V3 plan, still out of scope and untouched: LaTeX and HTML source adapters, the Level 1–3 staged reading levels, claim cards, the Research Review skill, and the writing feedback loop. The V2 pipeline in `process.py` is unchanged, and triage does not yet gate entry to it — a `deep_processing: "no"` card is a recommendation, not a lock.