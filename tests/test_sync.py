from __future__ import annotations

import json

from paperflow.config import Config, load_manifest
from paperflow.sync import changes, synchronize


def paper(**overrides):
    value = {
        "zotero_key": "ABCD1234",
        "citekey": "vaswani2017attention",
        "item_type": "journalArticle",
        "title": "Attention Is All You Need",
        "authors": ["Ashish Vaswani", "Noam Shazeer"],
        "date": "2017",
        "venue": "NeurIPS",
        "doi": "10.0000/example",
        "url": "https://example.test/paper",
        "abstract": "A transformer architecture.",
        "tags": ["transformer"],
        "source_modified_at": "2026-01-01T00:00:00Z",
        "annotations": [],
    }
    value.update(overrides)
    return value


def test_sync_is_idempotent_and_writes_manifest(tmp_path):
    config = Config(tmp_path)
    first = synchronize(config, [paper()])
    second = synchronize(config, [paper()])
    assert first.created == 1
    assert second.unchanged == 1
    assert second.created == second.updated == 0
    manifest = load_manifest(config)
    assert manifest["items"]["ABCD1234"]["note_path"] == "01-Literature/vaswani2017attention.md"
    json.loads(config.manifest_path.read_text(encoding="utf-8"))


def test_metadata_and_annotations_update_without_touching_my_notes(tmp_path):
    config = Config(tmp_path)
    synchronize(config, [paper()])
    note = config.literature_path / "vaswani2017attention.md"
    note.write_text(
        note.read_text(encoding="utf-8") + "A connection I want to keep.\n", encoding="utf-8"
    )
    changed = paper(
        title="Attention Is All You Need (updated)",
        source_modified_at="2026-01-02T00:00:00Z",
        annotations=[
            {
                "key": "ANN1",
                "type": "highlight",
                "page": "3",
                "color": "#ffd400",
                "text": "Multi-head attention.",
                "comment": "Compare heads.",
                "sort_index": "0001",
            }
        ],
    )
    result = synchronize(config, [changed])
    text = note.read_text(encoding="utf-8")
    assert result.updated == 1
    assert "Attention Is All You Need (updated)" in text
    assert "Multi-head attention." in text
    assert "A connection I want to keep." in text
    assert text.count("paperflow:begin metadata") == 1
    assert text.count("paperflow:begin annotations") == 1


def test_missing_note_is_recreated(tmp_path):
    config = Config(tmp_path)
    synchronize(config, [paper()])
    note = config.literature_path / "vaswani2017attention.md"
    note.unlink()
    result = synchronize(config, [paper()])
    assert result.created == 1
    assert note.exists()


def test_status_counts_annotation_only_changes(tmp_path):
    config = Config(tmp_path)
    synchronize(config, [paper()])
    changed = paper(
        annotations=[
            {
                "key": "ANN1",
                "type": "highlight",
                "page": "1",
                "color": "#ffd400",
                "text": "New evidence.",
                "comment": "",
                "sort_index": "0001",
            }
        ]
    )

    pending, new_annotations, missing = changes([changed], load_manifest(config), config)

    assert (pending, new_annotations, missing) == (1, 1, 0)
