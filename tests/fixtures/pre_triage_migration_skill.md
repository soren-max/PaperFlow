---
name: paperflow
description: Work in a PaperFlow Markdown research vault to review recently synced Zotero literature, build or update cross-paper concepts, synthesize a topic, maintain open research questions, or recommend what to read next. Use for research knowledge work in a vault with 01-Literature, 02-Concepts, 03-Synthesis, and 04-Questions; do not use it to edit Zotero or fabricate missing paper evidence.
---

# PaperFlow Research Agent

Treat the vault as a small evidence-to-reasoning system:

- `01-Literature/` is the evidence layer: one source-grounded note per Zotero item, named by stable citekey.
- `02-Concepts/` is the reasoning layer for stable ideas that accumulate across papers.
- `03-Synthesis/` is the reasoning layer for a question- or topic-specific cross-paper account.
- `04-Questions/` holds unresolved questions, working hypotheses, and research directions.

Read `AGENTS.md` before working. Search existing notes and aliases before creating a file. Prefer updating the closest existing Concept, Synthesis, or Question. Use the light templates in `90-Templates/` when creating a note, adapting them rather than filling empty sections mechanically.

## Evidence boundary

Zotero remains the bibliographic source of truth. Do not invent or repair metadata, quotes, findings, methods, citations, or page references from memory. Do not infer beyond the text available in Literature notes and user-provided sources.

Do not write AI inference into PaperFlow-managed Literature content. Do not modify `## My Notes` unless the user explicitly asks. Put cross-paper interpretation in Concepts or Synthesis and label it as synthesis, inference, hypothesis, uncertainty, or missing evidence when appropriate.

Every derived claim must remain traceable. Cite Literature with its exact stable citekey, normally as an Obsidian link such as `[[vaswani2017attention]]`. Preserve distinct sources even when they support the same point. A citation shows provenance; it does not make an unsupported statement true.

## Review recently synced papers

When asked to process or review recent papers:

1. Identify newly created or updated files in `01-Literature/`. Prefer current Git changes when available; otherwise compare Literature file modification times with `.paperflow/manifest.json` and its `last_sync_at` value.
2. State when this is only a time-based approximation. The manifest records synchronization, not whether a human or agent has read a paper, so never claim that a note is unprocessed solely from manifest state.
3. Read available titles, metadata, abstracts, and annotations; quickly group themes and point out thin evidence.
4. Recommend a short prioritized reading list with a concrete reason for each choice. Do not manufacture summaries when the note contains insufficient evidence.
5. Create or update reasoning notes only when the user asks, or when the request clearly includes processing into the knowledge base.

## Synthesize literature

When asked to synthesize papers on a topic:

1. Search `01-Literature/` by title, abstract, tags, annotations, citekey, and relevant synonyms. Use only the sources actually found and read.
2. Search `03-Synthesis/` for an existing note on the same question or topic and update it when practical.
3. Separate consensus, disagreements, method differences, evidence, limitations, and open questions. Distinguish paper-reported claims from your cross-paper interpretation.
4. Write the durable result to `03-Synthesis/`, using `90-Templates/Synthesis.md` as a starting point and exact citekeys throughout.
5. In `## Sources`, list only Literature notes used, one exact citekey link per source.

## Build or update a concept

When asked to establish a concept:

1. Search `02-Concepts/` by title, aliases, and related terms; update an existing concept instead of creating a synonym duplicate.
2. Read the relevant Literature and existing Synthesis notes before writing.
3. Put source-grounded statements under Evidence with exact citekeys. Put the compressed cross-paper understanding under Definition and Key Ideas, marking disputed or inferred points.
4. Link related Literature, Concepts, Synthesis, and Questions. Keep open issues explicit.
5. Write the result to `02-Concepts/` using `90-Templates/Concept.md` as a starting point.

## Recommend what to read next

Use the current Literature, Concepts, Questions, and gaps or limitations recorded in Synthesis. Return a limited ranked list, usually three to five papers, with the citekey and a vault-specific reason for each. Favor papers that resolve an open question, test a weak assumption, represent a disagreement, or fill a missing method/evidence gap. Say when the vault does not contain enough evidence to rank confidently.

## Maintain questions

Put durable unresolved questions or hypotheses in `04-Questions/`. Update a matching question when one exists. Keep evidence separate from working hypotheses, link the exact supporting or conflicting citekeys, and record what observation or reading would resolve the question. Do not present a hypothesis as a paper finding.

## Process a completed paper (V2)

Use this workflow when asked to read a paper deeply. `paperflow sync` still owns Zotero metadata and annotations; `paperflow ingest <citekey>` reads the PDF attached to the Zotero item and creates page-located Markdown in `.paperflow/papers/<zotero-key>/`. Install `paperflow[pdf]` once if PyMuPDF4LLM is absent. The PDF remains in Zotero.

Run `paperflow process <citekey>` to inspect durable progress. Work in this order, reading each prompt in `prompts/` immediately before its stage:

1. `paper-map.md`: use `state.json`, `structure.json`, abstract, headings, captions, conclusion, and limitations to write `paper-map.md` plus `paper-map.json` with exact `reading_sections` IDs.
2. `section-evidence.md`: call `paperflow process <citekey> --section <id>` and read only that section's listed chunks, one at a time. Write `evidence/<id>.jsonl`; run `paperflow process` to validate each section. All evidence quotes must occur on the cited page.
3. `cards.md`: use validated `evidence.jsonl` to create `method-card.md` and `result-card.md`, citing evidence IDs.
4. `paper-synthesis.md`: create `paper-note.md` from the map and cards, validate, then publish into the existing Literature note before `## My Notes`.
5. `knowledge-integration.md`: search and update existing Concepts, Questions, and Research Area MOCs only where evidence warrants it. Persist `knowledge-integration.md` with links to changes, then run `paperflow process` once more.

Resume from the first pending stage shown in `state.json`; completed section files are reusable. Do not read `source.md` all at once or create paper evidence from memory. When the converter garbles a table, equation, or figure, inspect that PDF page directly and record uncertainty. Keep research inference out of `evidence.jsonl` and label it in knowledge notes.

## Migrate a legacy paper (V2)

Read `prompts/legacy-migration.md` before processing an existing Literature note. Run `paperflow migrate <citekey>` first to capture the legacy `## My Notes` boundary and linked knowledge files. Then use the staged paper workflow above. Compare old claims with evidence IDs in `migration-review.md`, publish only a validated V2 reading block, and rerun `paperflow migrate <citekey>` to check preservation. Leave Concept, Question and Synthesis judgments in place until a human reviews their evidence. Never run this as a Vault-wide batch migration.
