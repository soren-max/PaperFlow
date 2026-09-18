from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from paperflow.cli import app
from paperflow.config import Config
from paperflow.ingest import ingest
from paperflow.process import inspect, publish_note
from paperflow.sync import synchronize


def _paper():
    return {
        "zotero_key": "ABCD1234",
        "citekey": "example2026",
        "title": "Example Paper",
        "authors": ["A Researcher"],
        "date": "2026",
        "abstract": "An example.",
        "source_modified_at": "2026-01-01",
        "annotations": [],
    }


def _ingested(tmp_path, monkeypatch, pages=None):
    config = Config(tmp_path)
    synchronize(config, [_paper()])
    pdf = tmp_path / "paper.pdf"
    pdf.write_bytes(b"fake PDF bytes")
    monkeypatch.setattr(
        "paperflow.ingest.fetch_paper_pdf",
        lambda key: {
            "zotero_key": key,
            "title": "Example Paper",
            "abstract": "An example.",
            "pdfs": [{"key": "PDF12345", "path": str(pdf)}],
        },
    )
    monkeypatch.setattr(
        "paperflow.ingest._pymupdf_pages",
        lambda path: (
            pages
            or [
                "# Example Paper\n\n## 1 Introduction\n\nThe method reads a graph.",
                "## 2 Results\n\nThe system scores 81.0 F1.",
            ]
        ),
    )
    directory, created = ingest(config, "example2026")
    assert created
    return config, directory


def test_ingest_is_resumable_and_locates_sections(tmp_path, monkeypatch):
    config, directory = _ingested(tmp_path, monkeypatch)
    assert "<!-- page: 2 -->" in (directory / "source.md").read_text(encoding="utf-8")
    structure = json.loads((directory / "structure.json").read_text(encoding="utf-8"))
    assert structure["page_count"] == 2
    assert any(
        section["title"] == "2 Results" and section["page_start"] == 2
        for section in structure["sections"]
    )
    assert ingest(config, "ABCD1234") == (directory, False)


def test_evidence_validation_resume_and_publish_preserves_my_notes(tmp_path, monkeypatch):
    config, directory = _ingested(tmp_path, monkeypatch)
    sections = json.loads((directory / "structure.json").read_text(encoding="utf-8"))["sections"]
    result = next(section for section in sections if section["title"] == "2 Results")
    (directory / "paper-map.md").write_text("# Paper map\n\nRead results.\n", encoding="utf-8")
    (directory / "paper-map.json").write_text(
        json.dumps({"reading_sections": [result["id"]]}), encoding="utf-8"
    )
    evidence = directory / "evidence"
    evidence.mkdir()
    card = {
        "id": "E001",
        "paper": "example2026",
        "section_id": result["id"],
        "page": 2,
        "type": "result",
        "claim": "The system scores 81.0 F1.",
        "evidence_quote": "The system scores 81.0 F1.",
        "source_chunk": result["chunks"][0]["path"],
        "confidence": "high",
    }
    (evidence / f"{result['id']}.jsonl").write_text(json.dumps(card) + "\n", encoding="utf-8")
    _, state, issues = inspect(config, "example2026")
    assert not issues
    assert state["stages"]["evidence_extracted"] == "done"

    (directory / "method-card.md").write_text("# Method\n\n[E001]", encoding="utf-8")
    (directory / "result-card.md").write_text("# Result\n\n[E001]", encoding="utf-8")
    (directory / "paper-note.md").write_text("## V2 Reading\n\n81.0 F1 [E001].\n", encoding="utf-8")
    note = config.literature_path / "example2026.md"
    note.write_text(note.read_text(encoding="utf-8") + "Personal observation.\n", encoding="utf-8")
    assert publish_note(config, "example2026") == note
    text = note.read_text(encoding="utf-8")
    assert text.index("## V2 Reading") < text.index("## My Notes")
    assert "Personal observation." in text
    _, state, issues = inspect(config, "example2026")
    assert not issues
    assert state["stages"]["literature_published"] == "done"
    (directory / "knowledge-integration.md").write_text("Reviewed.\n", encoding="utf-8")
    _, state, issues = inspect(config, "example2026")
    assert not issues
    assert state["stages"]["knowledge_integrated"] == "done"
    assert publish_note(config, "example2026") == note
    assert note.read_text(encoding="utf-8") == text
    changed = _paper()
    changed["title"] = "Example Paper, revised in Zotero"
    changed["source_modified_at"] = "2026-01-02"
    synchronize(config, [changed])
    updated = note.read_text(encoding="utf-8")
    assert "Example Paper, revised in Zotero" in updated
    assert "81.0 F1 [E001]." in updated
    assert "Personal observation." in updated
    note.write_text(
        updated.replace("81.0 F1 [E001].", "changed without evidence"), encoding="utf-8"
    )
    _, state, issues = inspect(config, "example2026")
    assert "Literature V2 block differs from paper-note.md" in issues
    assert state["stages"]["literature_published"] == "pending"
    assert state["stages"]["knowledge_integrated"] == "pending"


def test_wrong_evidence_page_is_rejected(tmp_path, monkeypatch):
    config, directory = _ingested(tmp_path, monkeypatch)
    section = next(
        section
        for section in json.loads((directory / "structure.json").read_text(encoding="utf-8"))[
            "sections"
        ]
        if section["title"] == "2 Results"
    )
    (directory / "paper-map.md").write_text("# Map\n", encoding="utf-8")
    (directory / "paper-map.json").write_text(
        json.dumps({"reading_sections": [section["id"]]}), encoding="utf-8"
    )
    (directory / "evidence").mkdir()
    card = {
        "id": "E001",
        "paper": "example2026",
        "section_id": section["id"],
        "page": 1,
        "type": "result",
        "claim": "Wrong page",
        "evidence_quote": "81.0 F1",
        "source_chunk": section["chunks"][0]["path"],
        "confidence": "high",
    }
    (directory / "evidence" / f"{section['id']}.jsonl").write_text(
        json.dumps(card) + "\n", encoding="utf-8"
    )
    _, state, issues = inspect(config, "example2026")
    assert issues
    assert state["sections"][section["id"]] == "invalid"
    with pytest.raises(ValueError):
        publish_note(config, "example2026")
    monkeypatch.setattr("paperflow.cli._get_config", lambda vault=None: config)
    result = CliRunner().invoke(app, ["process", "example2026"])
    assert result.exit_code == 1
    assert "page outside section" in result.output


def test_quote_must_occur_on_cited_page_within_section(tmp_path, monkeypatch):
    config, directory = _ingested(
        tmp_path,
        monkeypatch,
        ["# Example Paper\n\n## 1 Results\n\nOn first page.", "On second page 81.0 F1."],
    )
    section = next(
        section
        for section in json.loads((directory / "structure.json").read_text(encoding="utf-8"))[
            "sections"
        ]
        if section["title"] == "1 Results"
    )
    (directory / "paper-map.md").write_text("# Map\n", encoding="utf-8")
    (directory / "paper-map.json").write_text(
        json.dumps({"reading_sections": [section["id"]]}), encoding="utf-8"
    )
    (directory / "evidence").mkdir()
    card = {
        "id": "E001",
        "paper": "example2026",
        "section_id": section["id"],
        "page": 1,
        "type": "result",
        "claim": "A result",
        "evidence_quote": "81.0 F1",
        "source_chunk": section["chunks"][0]["path"],
        "confidence": "high",
    }
    (directory / "evidence" / f"{section['id']}.jsonl").write_text(
        json.dumps(card) + "\n", encoding="utf-8"
    )
    _, state, issues = inspect(config, "example2026")
    assert any("quote does not occur on page 1" in issue for issue in issues)
    assert state["sections"][section["id"]] == "invalid"
