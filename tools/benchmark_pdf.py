"""Small, reproducible converter comparison for one local academic PDF.

Run with optional converter packages installed. Output stays outside the vault.
"""

from __future__ import annotations

import argparse
import json
import re
import time
from importlib.metadata import version
from pathlib import Path


def docling_pages(path: Path) -> list[str]:
    from docling.document_converter import DocumentConverter

    document = DocumentConverter().convert(str(path)).document
    return [document.export_to_markdown(page_no=page) for page in sorted(document.pages)]


def pymupdf_pages(path: Path) -> list[str]:
    import pymupdf4llm

    return [entry["text"] for entry in pymupdf4llm.to_markdown(str(path), page_chunks=True)]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    results = {}
    for name, package, convert in (
        ("docling", "docling", docling_pages),
        ("pymupdf4llm", "pymupdf4llm", pymupdf_pages),
    ):
        start = time.perf_counter()
        try:
            pages = convert(args.pdf)
            elapsed = round(time.perf_counter() - start, 2)
            text = "\n\n".join(
                f"<!-- page: {number} -->\n\n{page}" for number, page in enumerate(pages, start=1)
            )
            (args.output / f"{name}.md").write_text(text, encoding="utf-8")
            results[name] = {
                "version": version(package),
                "seconds": elapsed,
                "pages": len(pages),
                "characters": len(text),
                "headings": len(re.findall(r"(?m)^#{1,6} ", text)),
                "markdown_table_rows": len(re.findall(r"(?m)^\|.*\|$", text)),
                "anchors": {
                    anchor: anchor in text
                    for anchor in ("81.0", "69.8", "92.15", "33.00", "0.89", "2.63")
                },
            }
        except Exception as error:  # the benchmark reports an unavailable backend
            results[name] = {"error": f"{type(error).__name__}: {error}"}
    (args.output / "results.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
