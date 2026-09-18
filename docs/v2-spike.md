# PaperFlow V2 architecture spike

## Existing V1 boundary

`paperflow init`, `sync`, `status`, and `doctor` retain their roles. `sync` reads Zotero metadata and annotations into clean Literature notes, preserves the managed-block boundary and `## My Notes`, and uses the manifest for stable citekeys. Zotero remains the bibliographic and PDF source of truth. `setup-windows.ps1` continues to install the lightweight base tool.

## New staged flow

```text
Zotero item + its PDF
  -> paperflow ingest <citekey>
  -> .paperflow/papers/<zotero-key>/source.md + structure.json + state.json
  -> paper-map.md + paper-map.json
  -> section chunks -> evidence/<section-id>.jsonl -> evidence.jsonl
  -> method-card.md + result-card.md
  -> paper-note.md -> existing 01-Literature note (before My Notes)
  -> existing Concepts / Questions / Research Area links
  -> knowledge-integration.md
```

`paperflow process <citekey>` reconciles stage state from durable files and shows the next step. `--section <id>` lists only that section's bounded chunk paths; `--publish-note` inserts a validated reading block into the existing Literature note. The included Codex skill controls the reasoning stages through versioned prompts. PaperFlow owns deterministic PDF location, conversion, section splitting, checksums, evidence validation, state reconciliation, and safe publication; it does not own an LLM runtime. No database or second PDF copy is introduced.

## KG-Agent result

Zotero item `J68KBEZ6` and attachment `WESJ8G7U` produced 19 page-marked pages and 32 bounded chunks. The reading plan selected 15 sections. The final artifacts contain 37 evidence cards, method and result cards, a compressed Literature block, and a knowledge integration log. Every evidence quote was checked against its chunk and page; important result tables were checked against PDF pages 6–8 and 18. The Literature note keeps the managed Zotero blocks and prior `## My Notes` intact.

The cards preserve the central method as stepwise tool selection, KG execution, and memory update, trained through programs derived from annotated KGQA queries. They record WebQSP 81.0 F1, CWQ 69.8 F1, KQA Pro 92.15 accuracy, out-of-domain limits, and the approximate latency comparison with dataset/metric context. The author Limitations text about backbone coverage conflicts with Table 7's additional backbone rows, so the note keeps both references. It also includes the omitted safety post-processing limitation and labels incomplete-KG implications as research inference.

## Context and recovery

The raw source is about 80k characters. Each generated source chunk is capped near 12k characters, and the KG-Agent selected sections are read sequentially. The paper map uses title, abstract, headings, captions, conclusion, and limitations. Evidence files are written per section, so rerunning `paperflow process` validates completed sections and lists only pending ones. Later cards and synthesis read the compact, validated evidence rather than reopening the PDF or full source. This bounds each reading step; it is not a measured token-saving percentage.

## Known limits and next phase

PDF-to-Markdown is imperfect: Figure 1's extracted image text is noisy and some table headers/cells are malformed. The evidence validator verifies location and exact quotation, not semantic correctness; critical numbers still need PDF-page review. `paper-map.json` selects sections manually, and the Codex skill writes reasoning artifacts; the CLI does not run an agent. This spike covers one ACL paper, so converter choice and prompts need a broader corpus check.

Next, benchmark more double-column, equation-heavy, and scanned papers; add a documented manual correction artifact for cases where a PDF page is right but extracted Markdown is wrong; strengthen card schemas and semantic QA while keeping the CLI small. Literature discovery, UI plugin, wiki plugin, and review writer remain later work.
