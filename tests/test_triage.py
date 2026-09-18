from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from paperflow import triage as triage_module
from paperflow.cli import app
from paperflow.config import Config
from paperflow.ingest import ingest
from paperflow.sync import synchronize
from paperflow.triage import CARD_SECTIONS, context_digest, summary, triage, validate_card

PDF_ONLY = "ZZPDFONLY"


def _paper(key: str = "ABCD1234", citekey: str = "example2026", **overrides) -> dict:
    item = {
        "zotero_key": key,
        "citekey": citekey,
        "title": f"{citekey} title",
        "authors": ["A Researcher"],
        "date": "2026",
        "venue": "ACL",
        "abstract": f"{citekey} studies graph retrieval under incomplete evidence.",
        "tags": ["retrieval", "knowledge-graph"],
        "doi": "10.1000/example",
        "source_modified_at": "2026-01-01",
        "annotations": [],
    }
    item.update(overrides)
    return item


def _synced(tmp_path, papers: list[dict] | None = None) -> Config:
    config = Config(tmp_path)
    synchronize(config, papers or [_paper()])
    return config


def _triage_dir(config: Config, key: str = "ABCD1234"):
    return config.state_dir / "triage" / key


def _card(**overrides) -> str:
    fields = {
        "paperflow_card": 1,
        "citekey": "example2026",
        "zotero_key": "ABCD1234",
        "research_area": "KG-augmented RAG",
        "priority": "high",
        "deep_processing": "yes",
        "basis": "abstract, tags",
    }
    fields.update(overrides)
    frontmatter = "\n".join(f"{name}: {value}" for name, value in fields.items())
    body = "\n\n".join(f"## {name}\n\nOne short {name.lower()} line." for name in CARD_SECTIONS)
    return f"---\n{frontmatter}\n---\n\n# Example\n\n{body}\n"


def _state(**overrides) -> dict:
    state = {"citekey": "example2026", "zotero_key": "ABCD1234", "sections_available": False}
    state.update(overrides)
    return state


def _write_card(config: Config, text: str, key: str = "ABCD1234"):
    directory = _triage_dir(config, key)
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "paper-card.md").write_text(text, encoding="utf-8")


def test_packet_uses_the_literature_note_without_the_pdf(tmp_path, monkeypatch):
    config = _synced(tmp_path)
    assert triage(config).ready == 1
    packet = (_triage_dir(config) / "packet.md").read_text(encoding="utf-8")
    assert "`example2026`" in packet
    assert "studies graph retrieval under incomplete evidence" in packet
    assert "retrieval, knowledge-graph" in packet
    assert "ACL" in packet
    assert "unavailable (paper is not ingested yet)" in packet
    assert PDF_ONLY not in packet
    state = json.loads((_triage_dir(config) / "state.json").read_text(encoding="utf-8"))
    assert state["sections_available"] is False
    assert state["card"] is None


def test_packet_records_a_missing_abstract_as_unavailable(tmp_path):
    config = _synced(tmp_path, [_paper(abstract="")])
    triage(config)
    packet = (_triage_dir(config) / "packet.md").read_text(encoding="utf-8")
    assert "## Abstract\n\nunavailable" in packet


def test_packet_gains_section_titles_once_ingested(tmp_path, monkeypatch):
    config = _synced(tmp_path)
    triage(config)
    pdf = tmp_path / "paper.pdf"
    pdf.write_bytes(b"fake PDF bytes")
    monkeypatch.setattr(
        "paperflow.ingest.fetch_paper_pdf",
        lambda key: {
            "zotero_key": key,
            "title": "Example",
            "abstract": "",
            "pdfs": [{"key": "PDF12345", "path": str(pdf)}],
        },
    )
    monkeypatch.setattr(
        "paperflow.ingest._pymupdf_pages",
        lambda path: [f"# Example Paper\n\n## 1 Introduction\n\n{PDF_ONLY} prose."],
    )
    ingest(config, "example2026")
    result = triage(config, refresh=True)
    assert result.rows[0].status == "ready"
    packet = (_triage_dir(config) / "packet.md").read_text(encoding="utf-8")
    assert "03-1-introduction  1 Introduction" in packet
    assert PDF_ONLY not in packet


def test_context_digest_reads_areas_questions_and_literature(tmp_path):
    config = _synced(tmp_path)
    (config.vault / "00-Research-Areas").mkdir()
    (config.vault / "00-Research-Areas/KG-RAG.md").write_text(
        "---\ntags: [graphs]\n---\n\n# KG-augmented Retrieval\n", encoding="utf-8"
    )
    (config.vault / "04-Questions").mkdir()
    (config.vault / "04-Questions/incomplete-kg.md").write_text(
        "---\nstatus: open\n---\n\n# How do methods behave under incomplete KGs?\n",
        encoding="utf-8",
    )
    digest = context_digest(config)
    assert "### Research Areas" in digest
    assert "KG-augmented Retrieval" in digest
    assert "How do methods behave under incomplete KGs?" in digest
    assert "- `example2026` — example2026 title — tags: retrieval, knowledge-graph" in digest


def test_context_digest_reports_omitted_entries(tmp_path, monkeypatch):
    monkeypatch.setattr(triage_module, "CONTEXT_ENTRIES", 2)
    papers = [_paper(key=f"KEY{index}", citekey=f"paper{index}") for index in range(5)]
    config = _synced(tmp_path, papers)
    assert "… 3 further Literature notes omitted" in context_digest(config)


def test_backlog_limit_leaves_the_rest_queued(tmp_path):
    papers = [_paper(key=f"KEY{index}", citekey=f"paper{index}") for index in range(3)]
    config = _synced(tmp_path, papers)
    result = triage(config, limit=2)
    assert len(result.rows) == 2
    assert result.ready == 2
    assert result.remaining == 1


def test_backlog_is_ordered_by_annotations_then_citekey(tmp_path):
    papers = [
        _paper(key="KEYA", citekey="alpha"),
        _paper(key="KEYB", citekey="beta"),
        _paper(
            key="KEYC",
            citekey="gamma",
            annotations=[
                {
                    "key": "A1",
                    "type": "highlight",
                    "page": "1",
                    "color": "",
                    "text": "important",
                    "comment": "",
                    "sort_index": "00001",
                }
            ],
        ),
    ]
    config = _synced(tmp_path, papers)
    assert [row.citekey for row in triage(config).rows] == ["gamma", "alpha", "beta"]


def test_a_resynced_note_makes_the_card_stale(tmp_path):
    config = _synced(tmp_path)
    triage(config)
    _write_card(config, _card())
    assert triage(config).rows[0].status == "card"
    changed = _paper(source_modified_at="2026-02-02", title="Revised title")
    synchronize(config, [changed])
    assert triage(config).rows[0].status == "stale"


def test_missing_literature_note_is_reported_not_raised(tmp_path):
    config = _synced(tmp_path)
    (config.vault / "01-Literature/example2026.md").unlink()
    result = triage(config)
    assert result.rows[0].status == "missing-note"
    assert result.missing_notes == ["01-Literature/example2026.md"]


def test_valid_card_is_accepted_and_summarized(tmp_path):
    config = _synced(tmp_path)
    triage(config)
    _write_card(config, _card())
    result = triage(config)
    assert result.rows[0].status == "card"
    assert not result.rows[0].issues
    assert (result.valid, result.high, result.recommended) == (1, 1, 1)
    counts = summary(config)
    assert counts == {"prepared": 1, "carded": 1, "high": 1, "recommended": 1, "pending": 0}


def test_summary_counts_a_packet_without_a_card_as_pending(tmp_path):
    config = _synced(tmp_path)
    triage(config)
    assert summary(config) == {
        "prepared": 1,
        "carded": 0,
        "high": 0,
        "recommended": 0,
        "pending": 1,
    }


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({"priority": "urgent"}, "priority must be one of"),
        ({"deep_processing": "maybe"}, "deep_processing must be yes or no"),
        ({"citekey": "someoneelse"}, "citekey does not match"),
        ({"research_area": ""}, "missing research_area"),
        ({"basis": "intuition"}, "unknown basis entries: intuition"),
        ({"basis": "abstract, sections"}, "section titles were not in this packet"),
    ],
)
def test_invalid_cards_are_rejected(tmp_path, overrides, expected):
    path = tmp_path / "paper-card.md"
    path.write_text(_card(**overrides), encoding="utf-8")
    issues, _ = validate_card(path, _state())
    assert any(expected in issue for issue in issues)


def test_card_sections_must_be_present_and_short(tmp_path):
    path = tmp_path / "paper-card.md"
    path.write_text(
        _card().replace("## Dataset\n\nOne short dataset line.\n\n", ""), encoding="utf-8"
    )
    issues, _ = validate_card(path, _state())
    assert any("missing an empty `## Dataset` section" in issue for issue in issues)

    path.write_text(_card().replace("One short method line.", "word " * 81), encoding="utf-8")
    issues, _ = validate_card(path, _state())
    assert any("`## Method` has 81 words (limit 80)" in issue for issue in issues)


def test_card_without_frontmatter_is_rejected(tmp_path):
    path = tmp_path / "paper-card.md"
    path.write_text("# Example\n", encoding="utf-8")
    issues, _ = validate_card(path, _state())
    assert any("no YAML frontmatter" in issue for issue in issues)


def test_triage_command_prepares_packets_and_reports(tmp_path, monkeypatch):
    config = _synced(tmp_path)
    monkeypatch.setattr("paperflow.cli._get_config", lambda vault=None: config)
    result = CliRunner().invoke(app, ["triage"])
    assert result.exit_code == 0, result.output
    assert "packet ready" in result.output
    assert "1 packets prepared" in result.output
    assert (_triage_dir(config) / "packet.md").is_file()


def test_triage_command_fails_on_an_invalid_card(tmp_path, monkeypatch):
    config = _synced(tmp_path)
    triage(config)
    _write_card(config, _card(priority="urgent"))
    monkeypatch.setattr("paperflow.cli._get_config", lambda vault=None: config)
    result = CliRunner().invoke(app, ["triage", "example2026"])
    assert result.exit_code == 1
    assert "priority must be one of" in result.output


def test_triage_command_reports_an_unknown_paper(tmp_path, monkeypatch):
    config = _synced(tmp_path)
    monkeypatch.setattr("paperflow.cli._get_config", lambda vault=None: config)
    result = CliRunner().invoke(app, ["triage", "nosuchpaper"])
    assert result.exit_code == 1
    assert "paperflow sync" in result.output
