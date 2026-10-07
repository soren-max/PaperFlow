from __future__ import annotations

import hashlib
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


def _synthesized(tmp_path, monkeypatch):
    config, directory = _ingested(tmp_path, monkeypatch)
    sections = json.loads((directory / "structure.json").read_text())["sections"]
    section = next(value for value in sections if value["title"] == "2 Results")
    plan = {
        "processing_level": "targeted",
        "reading_goal": "positioning",
        "target_contributions": ["evaluation"],
        "focus_questions": [{"question": "What result is reported?", "section_ids": [section["id"]]}],
        "reading_sections": [section["id"]],
        "positioning_path": "03-Synthesis/example2026-Positioning.md",
    }
    (directory / "paper-map.json").write_text(json.dumps(plan))
    (directory / "paper-map.md").write_text("# Map\nRead the reported result.\n")
    (directory / "evidence").mkdir()
    evidence = {
        "id": "E001", "paper": "example2026", "section_id": section["id"], "page": 2,
        "type": "result", "claim": "The system scores 81.0 F1.",
        "evidence_quote": "The system scores 81.0 F1.",
        "source_chunk": section["chunks"][0]["path"], "confidence": "high",
    }
    (directory / "evidence" / f"{section['id']}.jsonl").write_text(json.dumps(evidence) + "\n")
    for name in ("method-card.md", "result-card.md", "paper-note.md"):
        (directory / name).write_text("81.0 F1 [E001].\n")
    (directory / "knowledge-integration.md").write_text("Reviewed the affected claim.\n")
    return config, directory, plan


def _write_positioning(config, directory, plan):
    state = json.loads((directory / "state.json").read_text())
    card = config.vault / plan["positioning_path"]
    card.parent.mkdir(exist_ok=True)
    card.write_text(
        '---\ntype: positioning\ncitekey: example2026\nzotero_key: ABCD1234\n'
        'inference: true\nresearch_role: benchmark\nnovelty_threat: unknown\n'
        'reading_goal: positioning\ntarget_contributions: [evaluation]\n'
        f'source_sha256: {state["source_sha256"]}\n'
        f'evidence_sha256: {hashlib.sha256((directory / "evidence.jsonl").read_bytes()).hexdigest()}\n'
        '---\n# Positioning\n[[example2026]] reports 81.0 F1 [E001].\n'
        'Researcher inference: comparative value remains untested.\n'
    )
    return card


def test_positioning_resumes_without_polluting_literature(tmp_path, monkeypatch):
    config, directory, plan = _synthesized(tmp_path, monkeypatch)
    note = publish_note(config, "example2026")
    original = note.read_bytes()
    _, state, issues = inspect(config, "example2026")
    assert not issues
    assert state["stages"]["paper_synthesized"] == "done"
    assert state["stages"]["positioning_created"] == "pending"
    assert state["stages"]["knowledge_integrated"] == "pending"
    monkeypatch.setattr("paperflow.cli._get_config", lambda vault=None: config)
    result = CliRunner().invoke(app, ["process", "example2026"])
    assert result.exit_code == 0
    assert "prompts/positioning.md" in result.output
    _write_positioning(config, directory, plan)
    _, state, issues = inspect(config, "example2026")
    assert not issues
    assert state["stages"]["positioning_created"] == "done"
    assert state["stages"]["knowledge_integrated"] == "done"
    assert publish_note(config, "example2026") == note
    assert note.read_bytes() == original
    assert b"Researcher inference" not in original


@pytest.mark.parametrize(
    ("old", "new", "expected"),
    [
        ("inference: true", "inference: false", "inference: true"),
        ("[E001]", "[E999]", "valid evidence IDs"),
        ("citekey: example2026", "citekey: other", "citekey does not match"),
        ("target_contributions: [evaluation]", "target_contributions: [routing]", "differ from the reading plan"),
    ],
)
def test_invalid_positioning_cannot_finish_integration(tmp_path, monkeypatch, old, new, expected):
    config, directory, plan = _synthesized(tmp_path, monkeypatch)
    publish_note(config, "example2026")
    card = _write_positioning(config, directory, plan)
    card.write_text(card.read_text().replace(old, new))
    _, state, issues = inspect(config, "example2026")
    assert any(expected in issue for issue in issues)
    assert state["stages"]["paper_synthesized"] == "done"
    assert state["stages"]["knowledge_integrated"] == "pending"


def test_positioning_detects_revised_evidence(tmp_path, monkeypatch):
    config, directory, plan = _synthesized(tmp_path, monkeypatch)
    publish_note(config, "example2026")
    _write_positioning(config, directory, plan)
    section_id = plan["reading_sections"][0]
    evidence = directory / "evidence" / f"{section_id}.jsonl"
    evidence.write_text(evidence.read_text().replace('"confidence": "high"', '"confidence": "medium"'))
    _, state, issues = inspect(config, "example2026")
    assert any("evidence_sha256" in issue for issue in issues)
    assert state["stages"]["positioning_created"] == "pending"


@pytest.mark.parametrize("path", ["01-Literature/example2026.md", "03-Synthesis/../../outside.md"])
def test_positioning_cannot_target_source_or_outside_vault(tmp_path, monkeypatch, path):
    config, directory, plan = _synthesized(tmp_path, monkeypatch)
    original = (config.literature_path / "example2026.md").read_bytes()
    plan["positioning_path"] = path
    (directory / "paper-map.json").write_text(json.dumps(plan))
    _, _, issues = inspect(config, "example2026")
    assert any("inside 03-Synthesis" in issue for issue in issues)
    assert (config.literature_path / "example2026.md").read_bytes() == original


@pytest.mark.parametrize(
    ("question", "expected"),
    [
        ({"question": "Test?", "section_ids": ["missing"]}, "must be in reading_sections"),
        ({"question": "Test?", "section_ids": []}, "need missing_evidence"),
        ({"question": "Test?", "section_ids": [], "missing_evidence": True}, "need missing_evidence"),
        ({"question": "", "section_ids": []}, "nonempty question"),
    ],
)
def test_focus_questions_require_traceable_section_selection(tmp_path, monkeypatch, question, expected):
    config, directory, plan = _synthesized(tmp_path, monkeypatch)
    plan["focus_questions"] = [question]
    (directory / "paper-map.json").write_text(json.dumps(plan))
    _, state, issues = inspect(config, "example2026")
    assert any(expected in issue for issue in issues)
    assert state["stages"]["mapped"] == "pending"


def test_unlocated_focus_answer_keeps_its_evidence_gap(tmp_path, monkeypatch):
    config, directory, plan = _synthesized(tmp_path, monkeypatch)
    plan["focus_questions"].append({
        "question": "Does the system predict future graph state?",
        "section_ids": [],
        "missing_evidence": "No relevant section located; absence remains unverified.",
    })
    (directory / "paper-map.json").write_text(json.dumps(plan))
    _, state, issues = inspect(config, "example2026")
    assert not issues
    assert state["stages"]["mapped"] == "done"


def test_template_comments_do_not_count_as_positioning_evidence(tmp_path, monkeypatch):
    config, directory, plan = _synthesized(tmp_path, monkeypatch)
    publish_note(config, "example2026")
    card = _write_positioning(config, directory, plan)
    card.write_text(card.read_text().replace("[E001]", "<!-- [E001] -->"))
    _, state, issues = inspect(config, "example2026")
    assert any("valid evidence IDs" in issue for issue in issues)
    assert state["stages"]["knowledge_integrated"] == "pending"
