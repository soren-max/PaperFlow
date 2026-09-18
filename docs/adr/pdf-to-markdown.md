# ADR: PDF to Markdown for the V2 spike

Status: accepted for the current personal, Windows-first spike · 2026-09-18

## Decision

Use **PyMuPDF4LLM 1.28.2** as the default optional `paperflow ingest` converter. Keep **Docling 2.128.0** as a selectable alternative (`--converter docling`). The converter is not part of the V1 base install. Zotero keeps the PDF; PaperFlow records its locator, attachment key, checksum, page-marked Markdown, and bounded section chunks.

PyMuPDF4LLM was faster and preserved KG-Agent Table 7's model-to-score rows, which Docling merged. Both had extraction defects, so a PDF-page check remains required for important tables, equations, and figures. This is a one-paper choice, not a general accuracy ranking.

## Candidate screen

- [PyMuPDF4LLM](https://github.com/pymupdf/pymupdf4llm) provides local PDF conversion, page chunks, layout/table handling, and selective OCR on Windows. Its [license is AGPL-3.0](https://github.com/pymupdf/pymupdf4llm/blob/main/LICENSE).
- [Docling](https://github.com/docling-project/docling) provides a structured document model, Markdown and JSON export, table recognition, and local Windows execution. Its [code license is MIT](https://github.com/docling-project/docling/blob/main/LICENSE); model licenses are separate.
- [Marker](https://github.com/datalab-to/marker) and [MinerU](https://github.com/opendatalab/MinerU) are credible follow-up candidates. Marker uses model weights with distinct terms; MinerU offers different local tiers. Neither was installed or measured in this two-converter spike, so no performance claim is made about them.

## Benchmark setup

The source was the 19-page, two-column [ACL KG-Agent paper](https://aclanthology.org/2025.acl-long.468/) attached to Zotero item `J68KBEZ6` as PDF attachment `WESJ8G7U` (SHA-256 `816ef19ed31600292df6b71c91a9390910de5ba1a1ff18bca12d97634db315c5`). Windows 11 Pro, AMD Ryzen 9 8940HX, 16 GB RAM, local CPU path. `tools/benchmark_pdf.py` converted the *same local PDF* with both packages, emitted page-marked Markdown, timed conversion, and searched selected numeric anchors. PDF pages 6–8 and 18 were visually checked against the output.

Reproduce after installing the optional converter packages:

```powershell
python tools/benchmark_pdf.py "<Zotero PDF path>" "<output folder>"
```

| Converter | First run (s) | Cached run (s) | Markdown chars | Headings | Table rows | Six numeric anchors |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| PyMuPDF4LLM 1.28.2 | 26.3 | 6.05 | 79,995 | 31 | 101 | 6/6 |
| Docling 2.128.0 | 266.82 | 63.36 | 90,175 | 34 | 97 | 6/6 |

The first Docling run includes model download and cache setup; the first PyMuPDF4LLM run also includes startup effects. Cached timings were taken on the same machine after package/model installation. This is one run per condition, so the numbers show local experience rather than a statistical performance estimate. The anchor check confirms only that the strings occur somewhere; it does **not** establish correct row, column, or page attribution.

## Content assessment

| Criterion | PyMuPDF4LLM | Docling |
| --- | --- | --- |
| Two-column reading order | Main prose and Tables 2–5 follow a usable order. Some captions interrupt prose. | Main prose and Tables 2–5 follow a usable order. Some captions interrupt prose. |
| Section detection | 31 Markdown headings; one spurious `output.` heading. Manual paper map selects research sections. | 34 headings; section labels are cleaner in some places but still need review. |
| Tables | Tables 2–5, 7, and 10 retain checked result rows. Table 2's two-level header is distorted; Table 6 has malformed proportion cells. | Tables 2–5 and 10 retain checked values. Table 7 merges several model labels into one cell; Table 6 also has a malformed cell. |
| Figures/captions | Captions are retained, but extracted Figure 1 image text is noisy. | Captions are retained; the figure body is largely an image placeholder. |
| Equations | The KG formula is flattened into Markdown/text with superscript markup; mathematical fidelity was not established. | The formula is flattened into text; mathematical fidelity was not established. |
| Page provenance | `page_chunks=True` supplies page metadata; PaperFlow emits `<!-- page: N -->` and page ranges. | Per-page Markdown export works; Docling's internal document also has richer layout structure. |
| References | Present in output; bibliography parsing was not audited. | Present in output; bibliography parsing was not audited. |
| Windows/Python | Local pip install, no GPU requirement for this run, much shorter cached conversion. | Local pip install works, but many ML dependencies and first-run model downloads increase startup and disk cost. |
| License | AGPL-3.0; review distribution implications before a broad packaged release. | MIT code; check the specific model licenses used. |

## Safeguards and consequences

`source.md` is a machine-readable research source, separate from `01-Literature`. `structure.json` records section IDs, page ranges, line ranges, chunk paths, and chunk hashes. `state.json` records the PDF and source hashes and stage status. `paperflow process` verifies that source and chunks have not changed, then validates each evidence quote against its cited chunk **and page** before consolidating `evidence.jsonl`. It cannot establish that a paraphrase correctly interprets a table header or causal claim; that remains a reading QA step.

The default is provisional for personal research use. Before publishing PaperFlow as a broadly distributed V2 package, review the optional dependency's license fit and rerun the benchmark on more academic PDFs, including equation-heavy, scanned, and complex-table papers.
