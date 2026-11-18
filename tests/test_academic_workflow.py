"""Tests for academic workflow upgrades: Local API fallback, WSL paths, research links, and preservation."""

from __future__ import annotations

import hashlib
import http.client
import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from paperflow.cli import VAULT_RESOURCES, app
from paperflow.config import (
    Config,
    load_config,
    normalize_local_path,
    resolve_vault_relative_path,
    write_config,
)
from paperflow.ingest import ingest
from paperflow.migration import reconcile
from paperflow.positioning import validate_positioning
from paperflow.research import load_research_program, query_research
from paperflow.sync import synchronize
from paperflow.triage import context_digest, triage
from paperflow.zotero import (
    ZoteroUnavailable,
    fetch_paper_pdf,
    fetch_snapshot,
    list_collections,
    ping,
    zotero_context,
)


def _seed_synthetic_program(vault: Path, *, external_root: Path | None = None) -> tuple[Config, Path, Path]:
    """Create a synthetic research vault + 8-week research/experiments fixture (Demo fixture)."""
    root = external_root or vault
    research = root / "research"
    experiments = root / "experiments"
    (research / "weekly" / "week01").mkdir(parents=True, exist_ok=True)
    (experiments / "reports").mkdir(parents=True, exist_ok=True)

    (research / "RESEARCH_HOME.md").write_text(
        "# Research Home\n\n**当前 Week 1｜Synthetic Demo**\n",
        encoding="utf-8",
    )
    (research / "RESEARCH_STATE.md").write_text(
        "# Research State\n\nStage Week 1. Studying multi-agent handoff failures.\n",
        encoding="utf-8",
    )
    (research / "READING_ROADMAP.md").write_text(
        "# Roadmap\n\n"
        "| 周 | Research Question | 必读及精读目标 | 选读及用途 | 把阅读变成产出 |\n"
        "| --- | --- | --- | --- | --- |\n"
        "| 1 | RQ-01 · How do handoff failures arise in MAS? | **cemri2025mast** §3 | **agent2026** | Trace annotation |\n",
        encoding="utf-8",
    )
    (research / "HYPOTHESIS_REGISTRY.md").write_text(
        "# Hypothesis Registry\n\n"
        "| ID | 来源 | 假设 | 可证伪条件 | 证据 / 关联实验 |\n"
        "| --- | --- | --- | --- | --- |\n"
        "| H01 | Week 1 | Short handoffs drop scope constraints before downstream decisions. | "
        "If restoring scope constraints changes zero decisions, H01 fails. | EXP-001 |\n",
        encoding="utf-8",
    )
    (research / "IDEA_BOARD.md").write_text(
        "# Idea Board\n\n"
        "| 方向 | 现有证据 | 状态 / 下一动作 |\n"
        "| --- | --- | --- |\n"
        "| Scope constraint retention | [[cemri2025mast]] | Exploration |\n",
        encoding="utf-8",
    )
    (research / "EXPERIMENT_LEDGER.md").write_text(
        "# Experiment Ledger\n\n"
        "| 实验 ID / 日期 | 问题与假设 | 设计 / 基线 / 变量 | 模型与数据版本 | 状态 / 结果与 Trace | 替代解释 / 下一步 |\n"
        "| --- | --- | --- | --- | --- | --- |\n"
        "| EXP-001 / 2026-11-18 | RQ-01 / H01 | Compare vs [[cemri2025mast]] taxonomy | Synthetic Demo | Pass | Check Week 4 |\n",
        encoding="utf-8",
    )
    (research / "papers.jsonl").write_text(
        json.dumps(
            {
                "id": "cemri2025mast",
                "week": 1,
                "priority": "Core",
                "collection": "Evaluation-and-Benchmarks",
                "title": "Why Do Multi-Agent LLM Systems Fail?",
                "doi": "10.52202/085713-4082",
                "zotero_item_key": "4TM5XREY",
                "research_question_id": "RQ-01",
                "focus": "Failure taxonomy and trace labeling",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    (research / "weekly" / "week01" / "PLAN.md").write_text("# Week 1 Plan\n", encoding="utf-8")
    (experiments / "reports" / "EXP-001.md").write_text(
        "---\n"
        "experiment_id: EXP-001\n"
        "title: Synthetic Handoff Constraint Check (Demo)\n"
        "status: demo_completed\n"
        "rq_ids: [RQ-01]\n"
        "hypothesis_ids: [H01]\n"
        "baseline_papers: [cemri2025mast]\n"
        "challenged_papers: [agent2026]\n"
        "failure_modes: [condition_dropped]\n"
        "---\n\n"
        "# EXP-001 (Demo)\n\n"
        "Tests [[cemri2025mast]] failure taxonomy on H01; challenges [[agent2026]] assumption.\n",
        encoding="utf-8",
    )

    config = Config(
        vault=vault,
        research_dir=str(research.relative_to(vault)) if external_root is None else str(research),
        experiments_dir=(
            str(experiments.relative_to(vault)) if external_root is None else str(experiments)
        ),
    )
    return config, research, experiments


def test_portable_paths_handle_windows_wsl_and_file_uris():
    assert normalize_local_path(
        "file:///C:/Users/soren/Zotero/storage/LBV7V7VB/cemri2025mast.pdf",
        platform_name="posix",
    ) == Path("/mnt/c/Users/soren/Zotero/storage/LBV7V7VB/cemri2025mast.pdf")
    assert normalize_local_path(
        r"C:\Users\soren\Zotero\storage\LBV7V7VB\paper.pdf",
        platform_name="posix",
    ) == Path("/mnt/c/Users/soren/Zotero/storage/LBV7V7VB/paper.pdf")
    assert normalize_local_path(
        r"\\wsl.localhost\Ubuntu-26.04\home\soren\projects\idea_1117\long_research",
        platform_name="posix",
    ) == Path("/home/soren/projects/idea_1117/long_research")
    assert normalize_local_path(
        "file:///C:/Users/soren/paper.pdf",
        platform_name="nt",
    ) == Path("C:/Users/soren/paper.pdf")


def test_config_roundtrip_preserves_legacy_v1_and_new_fields(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    v1_vault = tmp_path / "v1"
    (v1_vault / ".paperflow").mkdir(parents=True)
    (v1_vault / ".paperflow" / "config.toml").write_text(
        f'vault = {json.dumps(str(v1_vault))}\nliterature_dir = "01-Literature"\n',
        encoding="utf-8",
    )
    loaded_v1 = load_config(v1_vault)
    assert loaded_v1.research_dir == ""
    assert loaded_v1.zotero_backend == "auto"

    vault = tmp_path / "v5"
    cfg = Config(
        vault=vault,
        collection_keys=("JSQ9B7XW",),
        research_dir="../external/research",
        experiments_dir="../external/experiments",
        zotero_backend="local_api",
        zotero_local_api_url="http://127.0.0.1:23119",
    )
    write_config(cfg)
    reloaded = load_config(vault)
    assert reloaded == cfg
    assert resolve_vault_relative_path("../external/research", vault) == (
        tmp_path / "external" / "research"
    ).resolve()


def test_zotero_local_api_fallback_reads_collections_items_annotations_and_pdf(monkeypatch):
    monkeypatch.setattr(
        "paperflow.zotero._run_zot",
        lambda *args, **kwargs: (_ for _ in ()).throw(ZoteroUnavailable("No token configured")),
    )

    routes = {
        "/api/users/0/collections?limit=1": (200, {}, "[]"),
        "/api/users/0/collections?start=0&limit=100": (
            200,
            {"Total-Results": "2"},
            json.dumps(
                [
                    {
                        "meta": {"numItems": 1},
                        "data": {"key": "ROOT1", "name": "Research-8Weeks", "parentCollection": False},
                    },
                    {
                        "meta": {"numItems": 1},
                        "data": {"key": "SUB1", "name": "Evaluation", "parentCollection": "ROOT1"},
                    },
                ]
            ),
        ),
        "/api/users/0/collections/ROOT1/items/top?start=0&limit=100": (
            200,
            {"Total-Results": "0"},
            "[]",
        ),
        "/api/users/0/collections/SUB1/items/top?start=0&limit=100": (
            200,
            {"Total-Results": "1"},
            json.dumps(
                [
                    {
                        "data": {
                            "key": "4TM5XREY",
                            "itemType": "conferencePaper",
                            "title": "Why Do Multi-Agent LLM Systems Fail?",
                            "creators": [{"firstName": "Mert", "lastName": "Cemri"}],
                            "date": "2025",
                            "conferenceName": "NeurIPS Datasets and Benchmarks",
                            "DOI": "10.52202/085713-4082",
                            "url": "https://example.test/mast",
                            "abstractNote": "Failure taxonomy.",
                            "tags": [{"tag": "mas"}],
                            "extra": "Citation Key: cemri2025mast",
                            "dateModified": "2026-11-18T10:00:00Z",
                        }
                    }
                ]
            ),
        ),
        "/api/users/0/items?itemType=annotation&start=0&limit=100": (
            200,
            {"Total-Results": "1"},
            json.dumps(
                [
                    {
                        "data": {
                            "key": "ANN1",
                            "parentItem": "LBV7V7VB",
                            "annotationType": "highlight",
                            "annotationPageLabel": "3",
                            "annotationColor": "#ffd400",
                            "annotationText": "Condition omitted in handoff.",
                            "annotationComment": "Check RQ-01",
                            "annotationSortIndex": "00001",
                        }
                    }
                ]
            ),
        ),
        "/api/users/0/items?itemType=attachment&start=0&limit=100": (
            200,
            {"Total-Results": "1"},
            json.dumps([{"data": {"key": "LBV7V7VB", "parentItem": "4TM5XREY"}}]),
        ),
        "/api/users/0/items/4TM5XREY": (
            200,
            {},
            json.dumps({"data": {"key": "4TM5XREY", "itemType": "conferencePaper", "title": "MAST"}}),
        ),
        "/api/users/0/items/4TM5XREY/children": (
            200,
            {},
            json.dumps(
                [
                    {
                        "data": {
                            "key": "LBV7V7VB",
                            "itemType": "attachment",
                            "contentType": "application/pdf",
                        }
                    }
                ]
            ),
        ),
        "/api/users/0/items/LBV7V7VB/file/view/url": (
            200,
            {},
            "file:///C:/Users/soren/Zotero/storage/LBV7V7VB/cemri2025mast.pdf",
        ),
    }

    class FakeResp:
        def __init__(self, status, headers, body):
            self.status = status
            self._headers = headers
            self._body = body.encode("utf-8")

        def getheaders(self):
            return list(self._headers.items())

        def read(self):
            return self._body

    class FakeConn:
        def __init__(self, netloc, timeout=30):
            self.path = ""

        def request(self, method, path, headers=None):
            assert method == "GET"
            self.path = path

        def getresponse(self):
            return FakeResp(*routes[self.path])

        def close(self):
            pass

    monkeypatch.setattr(http.client, "HTTPConnection", FakeConn)

    ok, detail = ping()
    assert (ok, detail) == (True, "local_api")
    cols = list_collections()
    assert [c.key for c in cols] == ["ROOT1", "SUB1"]
    items, selected = fetch_snapshot(("ROOT1",))
    assert len(items) == 1
    assert items[0]["citekey"] == "cemri2025mast"
    assert items[0]["venue"] == "NeurIPS Datasets and Benchmarks"
    assert items[0]["annotations"][0]["text"] == "Condition omitted in handoff."
    assert [c.key for c in selected] == ["ROOT1"]
    pdf_info = fetch_paper_pdf("4TM5XREY")
    assert pdf_info["pdfs"] == [
        {
            "key": "LBV7V7VB",
            "path": "file:///C:/Users/soren/Zotero/storage/LBV7V7VB/cemri2025mast.pdf",
        }
    ]


def test_ingest_translates_file_uri_pdf_locator(tmp_path, monkeypatch):
    vault = tmp_path / "vault"
    cfg = Config(vault)
    synchronize(
        cfg,
        [
            {
                "zotero_key": "4TM5XREY",
                "citekey": "cemri2025mast",
                "title": "MAST",
                "authors": ["Mert Cemri"],
                "date": "2025",
                "abstract": "Failure taxonomy.",
                "source_modified_at": "2026-01-01",
                "annotations": [],
            }
        ],
    )
    pdf = tmp_path / "cemri2025mast.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    monkeypatch.setattr(
        "paperflow.ingest.fetch_paper_pdf",
        lambda key: {
            "zotero_key": key,
            "title": "MAST",
            "abstract": "Failure taxonomy.",
            "pdfs": [{"key": "LBV7V7VB", "path": pdf.as_uri()}],
        },
    )
    monkeypatch.setattr(
        "paperflow.ingest._pymupdf_pages",
        lambda path: ["# MAST\n\n## 3 Method\n\nHandoff failure occurs."],
    )
    target, created = ingest(cfg, "cemri2025mast")
    assert created
    assert (target / "source.md").is_file()


def test_research_integration_links_papers_rqs_hypotheses_experiments_and_preserves_files(tmp_path, monkeypatch):
    vault = tmp_path / "vault"
    ext = tmp_path / "external_proj"
    cfg, research_dir, exp_dir = _seed_synthetic_program(vault, external_root=ext)
    write_config(cfg)

    paper = {
        "zotero_key": "4TM5XREY",
        "citekey": "cemri2025mast",
        "title": "Why Do Multi-Agent LLM Systems Fail?",
        "authors": ["Mert Cemri"],
        "date": "2025",
        "venue": "NeurIPS D&B",
        "doi": "10.52202/085713-4082",
        "abstract": "Taxonomy of multi-agent failures.",
        "tags": ["mas"],
        "source_modified_at": "2026-01-01",
        "annotations": [],
    }
    synchronize(cfg, [paper])
    note = cfg.literature_path / "cemri2025mast.md"
    note.write_text(note.read_text(encoding="utf-8") + "Student personal note.\n", encoding="utf-8")

    # Manual note alongside synced note
    manual = cfg.literature_path / "manual-cemri2025mast.md"
    manual.write_text(
        "---\ntype: literature\nsource_mode: manual\ndoi: \"10.52202/085713-4082\"\n---\n"
        "# MAST\n\nZotero 项目条目 `4TM5XREY`。\n\n## My Notes\n\nKeep me untouched.\n",
        encoding="utf-8",
    )

    # Evidence card & Positioning Card
    paper_dir = cfg.state_dir / "papers" / "4TM5XREY"
    paper_dir.mkdir(parents=True)
    (paper_dir / "source.md").write_text("<!-- page: 1 -->\nCondition dropped.\n", encoding="utf-8")
    source_hash = hashlib.sha256((paper_dir / "source.md").read_bytes()).hexdigest()
    evidence = {
        "id": "E001",
        "paper": "cemri2025mast",
        "section_id": "01-intro",
        "page": 4,
        "type": "result",
        "claim": "Condition dropped during inter-agent handoff.",
        "evidence_quote": "Condition dropped during inter-agent handoff.",
        "source_chunk": "sections/01-intro-01.md",
        "confidence": "high",
    }
    (paper_dir / "evidence.jsonl").write_text(json.dumps(evidence) + "\n", encoding="utf-8")
    evidence_hash = hashlib.sha256((paper_dir / "evidence.jsonl").read_bytes()).hexdigest()

    synth = vault / "03-Synthesis"
    synth.mkdir()
    pos_path = synth / "cemri2025mast-Positioning.md"
    pos_path.write_text(
        "---\n"
        "type: positioning\n"
        "citekey: cemri2025mast\n"
        "zotero_key: 4TM5XREY\n"
        "inference: true\n"
        "research_role: baseline\n"
        "novelty_threat: low\n"
        "reading_goal: experiment_design\n"
        "target_contributions: [handoff_trace]\n"
        "rq_ids: [RQ-01]\n"
        "hypothesis_ids: [H01]\n"
        "experiment_ids: [EXP-001]\n"
        "baseline_for: [EXP-001]\n"
        "challenged_by_experiments: []\n"
        f"source_sha256: {source_hash}\n"
        f"evidence_sha256: {evidence_hash}\n"
        "---\n"
        "# Positioning\n\n[[cemri2025mast]] shows condition dropped [E001].\n",
        encoding="utf-8",
    )

    assert validate_positioning(
        cfg,
        {"positioning_path": "03-Synthesis/cemri2025mast-Positioning.md", "target_contributions": ["handoff_trace"]},
        {"citekey": "cemri2025mast", "zotero_key": "4TM5XREY", "source_sha256": source_hash},
        [evidence],
    ) == pos_path.resolve()

    # Record hashes of research/ and My Notes to verify strictly read-only queries
    before_roadmap = (research_dir / "READING_ROADMAP.md").read_bytes()
    before_manual = manual.read_bytes()
    before_note = note.read_bytes()

    # Triage digest picks up external research program
    triage(cfg)
    digest = context_digest(cfg, citekey="cemri2025mast")
    assert "Active Research Program (read-only)" in digest
    assert "Current week: Week 1" in digest
    assert "RQ-01" in digest
    assert "H01" in digest

    # Query by Hypothesis, RQ, Paper, Experiment, Failure mode, Competitor
    by_hyp = query_research(cfg, "H01")
    assert by_hyp["hypotheses"][0]["id"] == "H01"
    assert by_hyp["papers"][0]["citekey"] == "cemri2025mast"
    assert by_hyp["experiments"][0]["id"] == "EXP-001"
    assert by_hyp["evidence"][0]["id"] == "E001"

    by_rq = query_research(cfg, "RQ-01")
    assert by_rq["rqs"][0]["id"] == "RQ-01"
    assert by_rq["experiments"][0]["id"] == "EXP-001"

    by_exp = query_research(cfg, "EXP-001")
    assert "cemri2025mast" in by_exp["experiments"][0]["baseline_papers"]
    assert "agent2026" in by_exp["experiments"][0]["challenged_papers"]
    assert any(p["citekey"] == "agent2026" and "EXP-001" in p["challenged_by_experiments"] for p in by_exp["papers"])

    by_phenom = query_research(cfg, "condition dropped", kind="evidence")
    assert len(by_phenom["evidence"]) == 1
    assert by_phenom["evidence"][0]["page"] == 4

    by_comp = query_research(cfg, "", kind="competitor")
    assert by_comp["positioning"][0]["research_role"] == "baseline"

    program = load_research_program(cfg)
    assert program.current_week == 1
    assert len(program.manual_notes) == 1
    assert program.manual_notes[0]["synced_citekey"] == "cemri2025mast"

    # CLI smoke checks (mocking only Zotero snapshot in status)
    monkeypatch.setattr("paperflow.cli.fetch_snapshot", lambda *args, **kwargs: (_ for _ in ()).throw(ZoteroUnavailable("offline")))
    runner = CliRunner()
    res_status = runner.invoke(app, ["status", "--vault", str(vault)])
    assert res_status.exit_code == 0, res_status.output
    assert "Week 1" in res_status.output

    res_research = runner.invoke(app, ["research", "--vault", str(vault), "--json"])
    assert res_research.exit_code == 0, res_research.output
    assert json.loads(res_research.output)["current_week"] == 1

    res_find = runner.invoke(app, ["find", "H01", "--vault", str(vault), "--json"])
    assert res_find.exit_code == 0, res_find.output
    assert json.loads(res_find.output)["papers"][0]["citekey"] == "cemri2025mast"

    # Strictly read-only: nothing mutated in research/, manual note, or My Notes
    assert (research_dir / "READING_ROADMAP.md").read_bytes() == before_roadmap
    assert manual.read_bytes() == before_manual
    assert note.read_bytes() == before_note


def test_graceful_degradation_when_zotero_and_research_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    vault = tmp_path / "bare_vault"
    cfg = Config(vault)
    write_config(cfg)
    monkeypatch.setattr(
        "paperflow.cli.fetch_snapshot",
        lambda *args, **kwargs: (_ for _ in ()).throw(ZoteroUnavailable("offline")),
    )
    runner = CliRunner()
    assert runner.invoke(app, ["status", "--vault", str(vault)]).exit_code == 0
    assert runner.invoke(app, ["research", "--vault", str(vault)]).exit_code == 0
    assert runner.invoke(app, ["find", "H01", "--vault", str(vault)]).exit_code == 0


def test_positioning_rejects_invalid_optional_link_lists(tmp_path):
    vault = tmp_path / "vault"
    (vault / "03-Synthesis").mkdir(parents=True)
    paper_dir = vault / ".paperflow" / "papers" / "ABCD1234"
    paper_dir.mkdir(parents=True)
    (paper_dir / "evidence.jsonl").write_text('{"id": "E001"}\n', encoding="utf-8")
    ev_hash = hashlib.sha256((paper_dir / "evidence.jsonl").read_bytes()).hexdigest()
    card = vault / "03-Synthesis" / "bad-Positioning.md"
    card.write_text(
        "---\n"
        "type: positioning\n"
        "citekey: ex2026\n"
        "zotero_key: ABCD1234\n"
        "inference: true\n"
        "research_role: baseline\n"
        "novelty_threat: low\n"
        "reading_goal: baseline\n"
        "target_contributions: []\n"
        "hypothesis_ids: H01\n"
        "source_sha256: s1\n"
        f"evidence_sha256: {ev_hash}\n"
        "---\n"
        "[[ex2026]] [E001]\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="hypothesis_ids must be an array"):
        validate_positioning(
            Config(vault),
            {"positioning_path": "03-Synthesis/bad-Positioning.md", "target_contributions": []},
            {"citekey": "ex2026", "zotero_key": "ABCD1234", "source_sha256": "s1"},
            [{"id": "E001"}],
        )


def test_init_preserves_research_config_and_custom_templates_and_installs_mentor_template(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    monkeypatch.setattr("paperflow.cli.ping", lambda timeout=5: (False, "offline"))
    monkeypatch.setattr("paperflow.cli.zotero_profile_found", lambda: False)

    vault = tmp_path / "Vault"
    cfg = Config(
        vault=vault,
        collection_keys=("JSQ9B7XW",),
        research_dir="research",
        experiments_dir="experiments",
        zotero_backend="local_api",
    )
    write_config(cfg)
    (vault / "90-Templates").mkdir(parents=True)
    (vault / "90-Templates" / "Positioning.md").write_text("custom positioning\n", encoding="utf-8")

    runner = CliRunner()
    res = runner.invoke(app, ["init", str(vault)])
    assert res.exit_code == 0, res.output
    reloaded = load_config(vault)
    assert reloaded.research_dir == "research"
    assert reloaded.experiments_dir == "experiments"
    assert reloaded.zotero_backend == "local_api"
    assert (vault / "90-Templates" / "Positioning.md").read_text(encoding="utf-8") == "custom positioning\n"
    assert (vault / "90-Templates" / "MentorReading.md").is_file()
    assert all((vault / path).is_file() for path in VAULT_RESOURCES)


def test_bridge_only_backend_does_not_fallback_and_reconcile_resolves_file_uri(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "paperflow.zotero._run_zot",
        lambda *args, **kwargs: (_ for _ in ()).throw(ZoteroUnavailable("bridge down")),
    )
    cfg_bridge = Config(tmp_path, zotero_backend="bridge")
    with zotero_context(cfg_bridge), pytest.raises(ZoteroUnavailable, match="bridge down"):
        list_collections()

    # Verify migration.reconcile handles file:// PDF locator without false drift
    cfg = Config(tmp_path / "mig")
    synchronize(
        cfg,
        [
            {
                "zotero_key": "K1234567",
                "citekey": "sample2026",
                "title": "Sample",
                "authors": ["Author"],
                "date": "2026",
                "abstract": "Abstract.",
                "source_modified_at": "2026-01-01",
                "annotations": [],
            }
        ],
    )
    pdf = tmp_path / "sample.pdf"
    pdf.write_bytes(b"pdf-bytes")
    pdir = cfg.state_dir / "papers" / "K1234567"
    pdir.mkdir(parents=True)
    (pdir / "state.json").write_text(
        json.dumps(
            {
                "zotero_key": "K1234567",
                "citekey": "sample2026",
                "note_path": "01-Literature/sample2026.md",
                "pdf_locator": pdf.as_uri(),
                "pdf_sha256": hashlib.sha256(b"pdf-bytes").hexdigest(),
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "paperflow.migration.inspect",
        lambda config, paper: (
            pdir,
            {"stages": {"literature_published": "done", "knowledge_integrated": "done"}},
            [],
        ),
    )
    _, result = reconcile(cfg, "sample2026")
    assert not result["issues"]
    assert result["status"] == "review_required"


def test_sync_and_research_queries_are_idempotent(tmp_path):
    vault = tmp_path / "vault"
    cfg, _, _ = _seed_synthetic_program(vault)
    paper = {
        "zotero_key": "4TM5XREY",
        "citekey": "cemri2025mast",
        "title": "Why Do Multi-Agent LLM Systems Fail?",
        "authors": ["Mert Cemri"],
        "date": "2025",
        "abstract": "Failure taxonomy.",
        "source_modified_at": "2026-01-01",
        "annotations": [],
    }
    first = synchronize(cfg, [paper])
    second = synchronize(cfg, [paper])
    assert first.created == 1
    assert second.unchanged == 1
    assert query_research(cfg, "H01") == query_research(cfg, "H01")
