from __future__ import annotations

import json
from hashlib import sha256

from paperflow.config import Config
from paperflow.migration import capture, reconcile
from paperflow.sync import synchronize


def test_legacy_capture_is_immutable_and_reconcile_detects_drift(tmp_path, monkeypatch):
    config = Config(tmp_path)
    synchronize(
        config,
        [
            {
                "zotero_key": "ABCD1234",
                "citekey": "sample2026",
                "title": "Sample",
                "authors": [],
                "date": "2026",
                "abstract": "Abstract.",
                "source_modified_at": "2026-01-01",
                "annotations": [],
            }
        ],
    )
    note = config.literature_path / "sample2026.md"
    note.write_text(note.read_text(encoding="utf-8") + "My old judgment.\n", encoding="utf-8")
    concept = tmp_path / "02-Concepts" / "Sample.md"
    concept.parent.mkdir()
    concept.write_text("Claim [[sample2026]]\n", encoding="utf-8")
    directory, baseline, created = capture(config, "sample2026")
    assert created
    assert baseline["legacy"]["assets"][0]["kind"] == "concept"
    _, result = reconcile(config, "sample2026")
    assert result["status"] == "pipeline_pending"
    assert result["my_notes_preserved"]

    note.write_text(
        note.read_text(encoding="utf-8").replace(
            "## My Notes", "The V2 section refers to `## My Notes`.\n\n## My Notes", 1
        ),
        encoding="utf-8",
    )
    _, result = reconcile(config, "sample2026")
    assert result["my_notes_preserved"]

    pdf = tmp_path / "sample.pdf"
    pdf.write_bytes(b"pdf")
    paper_dir = config.state_dir / "papers" / "ABCD1234"
    paper_dir.mkdir(parents=True)
    (paper_dir / "state.json").write_text(
        json.dumps(
            {
                "zotero_key": "ABCD1234",
                "citekey": "sample2026",
                "note_path": "01-Literature/sample2026.md",
                "pdf_locator": str(pdf),
                "pdf_sha256": sha256(b"pdf").hexdigest(),
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "paperflow.migration.inspect",
        lambda config, paper: (
            paper_dir,
            {"stages": {"literature_published": "done", "knowledge_integrated": "done"}},
            [],
        ),
    )
    review = directory / "migration-review.md"
    review.write_text("Decision: pending\n", encoding="utf-8")
    assert reconcile(config, "sample2026")[1]["status"] == "review_required"
    review.write_text("Decision: accepted\n", encoding="utf-8")
    assert reconcile(config, "sample2026")[1]["status"] == "migrated"
    review.write_text("Decision: rejected\n", encoding="utf-8")
    assert reconcile(config, "sample2026")[1]["status"] == "rejected"

    concept.write_text("Changed claim [[sample2026]]\n", encoding="utf-8")
    question = tmp_path / "04-Questions" / "Follow-up.md"
    question.parent.mkdir()
    question.write_text("Hypothesis [[sample2026]]\n", encoding="utf-8")
    note.write_text(note.read_text(encoding="utf-8") + "New personal note.\n", encoding="utf-8")
    _, repeated, created = capture(config, "ABCD1234")
    assert not created
    assert repeated == baseline
    _, result = reconcile(config, "sample2026")
    assert result["status"] == "conflict"
    assert result["changed_legacy_assets"] == ["02-Concepts/Sample.md"]
    assert result["new_legacy_assets"] == ["04-Questions/Follow-up.md"]
    assert not result["my_notes_preserved"]
    assert json.loads((directory / "migration.json").read_text(encoding="utf-8")) == baseline
