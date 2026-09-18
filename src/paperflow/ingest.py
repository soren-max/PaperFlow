"""Convert a Zotero PDF to bounded, page-located Markdown reading inputs."""

from __future__ import annotations

import hashlib
import json
import re
import tempfile
from importlib.metadata import version
from pathlib import Path

from .config import Config, load_manifest
from .zotero import fetch_paper_pdf

HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
PAGE = re.compile(r"^<!-- page: (\d+) -->$")
MAX_CHUNK_CHARACTERS = 12_000


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def resolve_paper(config: Config, paper: str) -> tuple[str, dict]:
    records = load_manifest(config).get("items", {})
    if paper in records:
        return paper, records[paper]
    matches = [(key, record) for key, record in records.items() if record.get("citekey") == paper]
    if len(matches) != 1:
        raise ValueError(f"Paper '{paper}' is not in the sync manifest. Run paperflow sync first.")
    return matches[0]


def _docling_pages(pdf: Path) -> list[str]:
    try:
        from docling.document_converter import DocumentConverter
    except ImportError as error:
        raise RuntimeError(
            "Docling is required. Install it with: pip install 'paperflow[pdf-docling]'"
        ) from error
    document = DocumentConverter().convert(str(pdf)).document
    return [document.export_to_markdown(page_no=page).strip() for page in sorted(document.pages)]


def _pymupdf_pages(pdf: Path) -> list[str]:
    try:
        import pymupdf4llm
    except ImportError as error:
        raise RuntimeError(
            "PyMuPDF4LLM is required. Install it with: pip install 'paperflow[pdf]'"
        ) from error
    return [entry["text"].strip() for entry in pymupdf4llm.to_markdown(str(pdf), page_chunks=True)]


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    return slug[:48] or "section"


def _split_chunks(lines: list[str]) -> list[str]:
    """Split on paragraph boundaries, preserving page markers in every chunk."""
    chunks: list[str] = []
    current: list[str] = []
    page_marker = ""
    for line in lines:
        if PAGE.match(line):
            page_marker = line
        if current and sum(len(part) + 1 for part in current) + len(line) > MAX_CHUNK_CHARACTERS:
            chunks.append("\n".join(current).strip() + "\n")
            current = [page_marker] if page_marker and line != page_marker else []
        current.append(line)
    if current:
        chunks.append("\n".join(current).strip() + "\n")
    return chunks


def _build_structure(source: str, output: Path) -> dict:
    lines = source.splitlines()
    headings = [
        (index, match) for index, line in enumerate(lines) if (match := HEADING.match(line))
    ]
    boundaries = [0, *(index for index, _ in headings), len(lines)]
    boundaries = sorted(set(boundaries))
    sections = []
    sections_dir = output / "sections"
    sections_dir.mkdir()
    current_page = 1
    page_at_line = []
    for line in lines:
        if match := PAGE.match(line):
            current_page = int(match.group(1))
        page_at_line.append(current_page)
    for ordinal, (start, end) in enumerate(
        zip(boundaries[:-1], boundaries[1:], strict=True), start=1
    ):
        if start == end:
            continue
        match = HEADING.match(lines[start])
        title = match.group(2) if match else "Front matter"
        section_id = f"{ordinal:02d}-{_slug(title)}"
        content_end = end
        while content_end > start and (
            not lines[content_end - 1].strip() or PAGE.match(lines[content_end - 1])
        ):
            content_end -= 1
        section_lines = lines[start:content_end]
        if not section_lines:
            continue
        if not PAGE.match(section_lines[0]):
            section_lines = [f"<!-- page: {page_at_line[start]} -->", "", *section_lines]
        chunks = []
        for chunk_number, chunk in enumerate(_split_chunks(section_lines), start=1):
            relative = f"sections/{section_id}-{chunk_number:02d}.md"
            (output / relative).write_text(chunk, encoding="utf-8")
            chunks.append(
                {
                    "path": relative,
                    "characters": len(chunk),
                    "sha256": hashlib.sha256(chunk.encode("utf-8")).hexdigest(),
                }
            )
        sections.append(
            {
                "id": section_id,
                "title": title,
                "level": len(match.group(1)) if match else 0,
                "page_start": page_at_line[start],
                "page_end": page_at_line[content_end - 1],
                "source_line_start": start + 1,
                "source_line_end": content_end,
                "chunks": chunks,
            }
        )
    return {"version": 1, "page_count": source.count("<!-- page: "), "sections": sections}


def ingest(config: Config, paper: str, converter: str = "pymupdf4llm") -> tuple[Path, bool]:
    key, record = resolve_paper(config, paper)
    zotero = fetch_paper_pdf(key)
    pdfs = [entry for entry in zotero.get("pdfs", []) if Path(entry["path"]).is_file()]
    if not pdfs:
        raise ValueError(f"Zotero item {key} has no locally available PDF attachment")
    if len(pdfs) > 1:
        raise ValueError(f"Zotero item {key} has multiple PDFs; choose one in Zotero first")
    attachment = pdfs[0]
    pdf = Path(attachment["path"])
    pdf_hash = _hash_file(pdf)
    target = config.state_dir / "papers" / key
    state_path = target / "state.json"
    if target.exists():
        if not state_path.exists():
            raise ValueError(f"{target} exists without state.json; inspect it before retrying")
        state = json.loads(state_path.read_text(encoding="utf-8"))
        if state.get("pdf_sha256") != pdf_hash or not (target / "source.md").is_file():
            raise ValueError(
                f"{target} has changed or incomplete source data; inspect it before retrying"
            )
        if state.get("converter", {}).get("name") != converter:
            raise ValueError(
                f"{target} was ingested with {state['converter']['name']}; "
                "inspect existing artifacts before choosing a different converter"
            )
        return target, False

    if converter == "pymupdf4llm":
        pages = _pymupdf_pages(pdf)
    elif converter == "docling":
        pages = _docling_pages(pdf)
    else:
        raise ValueError("Converter must be pymupdf4llm or docling")
    if not pages or not any(pages):
        raise ValueError(f"{converter} produced no readable text")
    source = (
        "\n\n".join(
            f"<!-- page: {number} -->\n\n{content}" for number, content in enumerate(pages, start=1)
        ).strip()
        + "\n"
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f".{key}-", dir=target.parent) as temporary:
        output = Path(temporary)
        (output / "source.md").write_text(source, encoding="utf-8")
        structure = _build_structure(source, output)
        _write_json(output / "structure.json", structure)
        _write_json(
            output / "state.json",
            {
                "version": 1,
                "zotero_key": key,
                "citekey": record["citekey"],
                "title": zotero["title"],
                "abstract": zotero.get("abstract", ""),
                "note_path": record["note_path"],
                "attachment_key": attachment["key"],
                "pdf_locator": str(pdf),
                "pdf_sha256": pdf_hash,
                "source_sha256": hashlib.sha256(source.encode("utf-8")).hexdigest(),
                "converter": {"name": converter, "version": version(converter)},
                "stages": {
                    "ingested": "done",
                    "mapped": "pending",
                    "paper_synthesized": "pending",
                    "knowledge_integrated": "pending",
                },
                "sections": {section["id"]: "pending" for section in structure["sections"]},
            },
        )
        output.rename(target)
    return target, True
