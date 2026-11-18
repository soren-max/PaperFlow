"""Read-only integration with external research roadmaps, hypotheses, and experiments."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .config import Config, load_manifest

FRONTMATTER_RE = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n?", re.DOTALL)
HEADING_RE = re.compile(r"(?m)^#\s+(.+?)\s*$")
RQ_ID_RE = re.compile(r"\bRQ-\d+\b")
HYPOTHESIS_ID_RE = re.compile(r"\bH\d{2,}\b")
EXPERIMENT_ID_RE = re.compile(r"\bEXP-[A-Za-z0-9_-]+\b")
WIKILINK_RE = re.compile(r"\[\[([^]|]+)(?:\|[^]]+)?\]\]")
WEEK_RE = re.compile(r"\bWeek\s*0*(\d+)\b", re.IGNORECASE)
ZOTERO_KEY_RE = re.compile(r"Zotero[^`\n]*`([A-Z0-9]{8})`")


def _split_frontmatter(text: str) -> tuple[dict, str]:
    match = FRONTMATTER_RE.match(text)
    if match is None:
        return {}, text
    try:
        data = yaml.safe_load(match.group(1))
    except yaml.YAMLError:
        return {}, text[match.end() :]
    return (data if isinstance(data, dict) else {}), text[match.end() :]


def _as_str_list(value: object) -> list[str]:
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def _parse_markdown_tables(text: str) -> list[dict[str, str]]:
    """Extract row dictionaries from every GitHub-flavored Markdown table in text."""
    rows: list[dict[str, str]] = []
    lines = text.splitlines()
    index = 0
    while index + 1 < len(lines):
        header_line = lines[index].strip()
        sep_line = lines[index + 1].strip()
        if (
            header_line.startswith("|")
            and sep_line.startswith("|")
            and re.fullmatch(r"[\s|:-]+", sep_line)
            and "-" in sep_line
        ):
            headers = [cell.strip() for cell in header_line.strip("|").split("|")]
            index += 2
            while index < len(lines) and lines[index].strip().startswith("|"):
                cells = [cell.strip() for cell in lines[index].strip().strip("|").split("|")]
                if len(cells) < len(headers):
                    cells.extend([""] * (len(headers) - len(cells)))
                rows.append(
                    {
                        header: cells[pos] if pos < len(cells) else ""
                        for pos, header in enumerate(headers)
                    }
                )
                index += 1
            continue
        index += 1
    return rows


def _extract_links(text: str) -> tuple[list[str], list[str], list[str], list[str]]:
    rqs = list(dict.fromkeys(RQ_ID_RE.findall(text)))
    hyps = list(dict.fromkeys(HYPOTHESIS_ID_RE.findall(text)))
    exps = list(dict.fromkeys(EXPERIMENT_ID_RE.findall(text)))
    wikilinks = list(dict.fromkeys(WIKILINK_RE.findall(text)))
    return rqs, hyps, exps, wikilinks


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def _parse_week_number(text: str) -> int | None:
    match = WEEK_RE.search(text)
    return int(match.group(1)) if match else None


@dataclass
class ResearchProgramSummary:
    research_dir: Path | None = None
    experiments_dir: Path | None = None
    current_week: int | None = None
    state_summary: str = ""
    rqs: list[dict] = field(default_factory=list)
    hypotheses: list[dict] = field(default_factory=list)
    ideas: list[dict] = field(default_factory=list)
    ledger_experiments: list[dict] = field(default_factory=list)
    corpus: list[dict] = field(default_factory=list)
    weekly_plans: list[str] = field(default_factory=list)
    experiment_reports: list[dict] = field(default_factory=list)
    manual_notes: list[dict] = field(default_factory=list)


def _load_corpus(research_dir: Path) -> list[dict]:
    jsonl = research_dir / "papers.jsonl"
    if not jsonl.is_file():
        return []
    entries: list[dict] = []
    for line in jsonl.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(entry, dict):
            entries.append(entry)
    return entries


def _load_experiment_reports(experiments_dir: Path | None) -> list[dict]:
    if not experiments_dir or not experiments_dir.is_dir():
        return []
    reports_dir = experiments_dir / "reports"
    if not reports_dir.is_dir():
        return []
    reports: list[dict] = []
    for path in sorted(reports_dir.glob("*.md")):
        raw = path.read_text(encoding="utf-8")
        fm, body = _split_frontmatter(raw)
        heading = HEADING_RE.search(body)
        rqs, hyps, exps, wikilinks = _extract_links(raw)
        exp_id = str(fm.get("experiment_id") or (exps[0] if exps else path.stem)).strip()
        reports.append(
            {
                "id": exp_id,
                "title": str(fm.get("title") or (heading.group(1) if heading else path.stem)),
                "status": str(fm.get("status") or ""),
                "path": path.as_posix(),
                "rq_ids": list(dict.fromkeys([*_as_str_list(fm.get("rq_ids")), *rqs])),
                "hypothesis_ids": list(
                    dict.fromkeys([*_as_str_list(fm.get("hypothesis_ids")), *hyps])
                ),
                "paper_citekeys": list(
                    dict.fromkeys([*_as_str_list(fm.get("paper_citekeys")), *wikilinks])
                ),
                "baseline_papers": _as_str_list(fm.get("baseline_papers")),
                "inspired_by": _as_str_list(fm.get("inspired_by")),
                "challenged_papers": _as_str_list(fm.get("challenged_papers")),
                "failure_modes": _as_str_list(fm.get("failure_modes")),
                "body": body,
            }
        )
    return reports


def detect_manual_notes(config: Config, corpus: list[dict] | None = None) -> list[dict]:
    """Identify manual Literature cards and match them to manifest or corpus entries."""
    if not config.literature_path.is_dir():
        return []
    manifest_items = load_manifest(config).get("items", {})
    manifest_notes = {entry.get("note_path", "") for entry in manifest_items.values()}
    corpus = corpus or []
    corpus_by_key = {
        str(entry.get("zotero_item_key")): entry
        for entry in corpus
        if entry.get("zotero_item_key")
    }
    corpus_by_doi = {
        str(entry.get("doi")).strip().casefold(): entry
        for entry in corpus
        if entry.get("doi")
    }
    hints: list[dict] = []
    for path in sorted(config.literature_path.glob("*.md")):
        relative = path.relative_to(config.vault).as_posix()
        if relative in manifest_notes:
            continue
        raw = path.read_text(encoding="utf-8")
        fm, _body = _split_frontmatter(raw)
        is_manual = path.name.startswith("manual-") or fm.get("source_mode") == "manual"
        if not is_manual:
            continue
        doi = str(fm.get("doi") or "").strip()
        zotero_match = ZOTERO_KEY_RE.search(raw)
        zotero_key = str(fm.get("zotero_key") or (zotero_match.group(1) if zotero_match else "")).strip()
        corpus_match = corpus_by_key.get(zotero_key) or (
            corpus_by_doi.get(doi.casefold()) if doi else None
        )
        synced_match = manifest_items.get(zotero_key) if zotero_key else None
        hints.append(
            {
                "path": relative,
                "stem": path.stem,
                "doi": doi,
                "zotero_key": zotero_key,
                "corpus_id": corpus_match.get("id") if corpus_match else None,
                "synced_citekey": synced_match.get("citekey") if synced_match else None,
                "synced_note_path": synced_match.get("note_path") if synced_match else None,
            }
        )
    return hints


def load_research_program(config: Config) -> ResearchProgramSummary:
    """Read linked research roadmap, hypotheses, corpus, and experiment reports without writes."""
    research_dir = config.research_path
    experiments_dir = config.experiments_path
    summary = ResearchProgramSummary(
        research_dir=research_dir if research_dir and research_dir.is_dir() else None,
        experiments_dir=experiments_dir if experiments_dir and experiments_dir.is_dir() else None,
    )
    if summary.research_dir:
        state_text = _read_text(summary.research_dir / "RESEARCH_STATE.md")
        home_text = _read_text(summary.research_dir / "RESEARCH_HOME.md")
        summary.current_week = _parse_week_number(state_text) or _parse_week_number(home_text)
        lines = [
            line.strip()
            for line in state_text.splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
        summary.state_summary = lines[0] if lines else ""

        roadmap_text = _read_text(summary.research_dir / "READING_ROADMAP.md")
        for row in _parse_markdown_tables(roadmap_text):
            rq_cell = row.get("Research Question", "")
            rq_match = RQ_ID_RE.search(rq_cell)
            if not rq_match:
                continue
            week_raw = row.get("周", "").strip()
            summary.rqs.append(
                {
                    "id": rq_match.group(0),
                    "week": int(week_raw) if week_raw.isdigit() else None,
                    "question": rq_cell,
                    "required_reading": row.get("必读及精读目标", ""),
                    "optional_reading": row.get("选读及用途", ""),
                    "deliverable": row.get("把阅读变成产出", ""),
                }
            )

        hyp_text = _read_text(summary.research_dir / "HYPOTHESIS_REGISTRY.md")
        for row in _parse_markdown_tables(hyp_text):
            hyp_id = row.get("ID", "").strip()
            if not hyp_id:
                continue
            summary.hypotheses.append(
                {
                    "id": hyp_id,
                    "source": row.get("来源", ""),
                    "statement": row.get("假设", ""),
                    "falsification": row.get("可证伪条件", ""),
                    "evidence": row.get("证据 / 关联实验", ""),
                }
            )

        idea_text = _read_text(summary.research_dir / "IDEA_BOARD.md")
        for row in _parse_markdown_tables(idea_text):
            direction = row.get("方向", "").strip()
            if not direction:
                continue
            summary.ideas.append(
                {
                    "direction": direction,
                    "evidence": row.get("现有证据", ""),
                    "status_next": row.get("状态 / 下一动作", ""),
                }
            )

        ledger_text = _read_text(summary.research_dir / "EXPERIMENT_LEDGER.md")
        for row in _parse_markdown_tables(ledger_text):
            exp_cell = row.get("实验 ID / 日期", "").strip()
            if not exp_cell:
                continue
            joined = " ".join(row.values())
            rqs, hyps, exps, wikilinks = _extract_links(joined)
            summary.ledger_experiments.append(
                {
                    "id": exps[0] if exps else exp_cell,
                    "label": exp_cell,
                    "rq_ids": rqs,
                    "hypothesis_ids": hyps,
                    "paper_citekeys": wikilinks,
                    "design": row.get("设计 / 基线 / 变量", ""),
                    "status_result": row.get("状态 / 结果与 Trace", ""),
                    "next_step": row.get("替代解释 / 下一步", ""),
                }
            )

        summary.corpus = _load_corpus(summary.research_dir)
        weekly_root = summary.research_dir / "weekly"
        if weekly_root.is_dir():
            summary.weekly_plans = [
                path.relative_to(summary.research_dir).as_posix()
                for path in sorted(weekly_root.glob("week*/PLAN.md"))
            ]

    summary.experiment_reports = _load_experiment_reports(summary.experiments_dir)
    summary.manual_notes = detect_manual_notes(config, summary.corpus)
    return summary


def render_research_digest(
    config: Config, *, citekey: str = "", zotero_key: str = "", doi: str = "", limit: int = 2000
) -> str:
    """Build a bounded read-only program summary for triage packets when research files exist."""
    program = load_research_program(config)
    if not program.research_dir and not program.experiments_dir:
        return ""
    lines = ["### Active Research Program (read-only)"]
    if program.current_week is not None:
        lines.append(f"- Current week: Week {program.current_week}")
    if program.state_summary:
        lines.append(f"- State: {program.state_summary[:240]}")
    if program.corpus:
        match = next(
            (
                entry
                for entry in program.corpus
                if (zotero_key and entry.get("zotero_item_key") == zotero_key)
                or (citekey and citekey in (entry.get("id"), entry.get("citation_key")))
                or (doi and entry.get("doi") and entry["doi"].casefold() == doi.casefold())
            ),
            None,
        )
        if match:
            lines.append(
                f"- Corpus match: `{match.get('id')}` · Week {match.get('week')} · "
                f"{match.get('priority')} · {match.get('research_question_id')} · "
                f"{match.get('focus', '')}"
            )
    if program.rqs:
        ordered_rqs = sorted(
            program.rqs,
            key=lambda item: (
                0 if item.get("week") == program.current_week else 1,
                item.get("week") or 99,
            ),
        )
        for rq in ordered_rqs[:4]:
            lines.append(f"- {rq['question'][:200]}")
    if program.hypotheses:
        for hyp in program.hypotheses[:4]:
            lines.append(f"- {hyp['id']}: {hyp['statement'][:200]}")
    if program.manual_notes:
        relevant = [
            hint for hint in program.manual_notes if not zotero_key or hint["zotero_key"] == zotero_key
        ]
        for hint in relevant[:2]:
            lines.append(
                f"- Manual note present: `{hint['path']}`"
                + (f" (zotero_key `{hint['zotero_key']}`)" if hint["zotero_key"] else "")
            )
    text = "\n".join(lines)
    if len(text) <= limit:
        return text
    return text[: limit - 20].rstrip() + "\n[… truncated]"


def _load_evidence_cards(config: Config, zotero_key: str) -> list[dict]:
    path = config.state_dir / "papers" / zotero_key / "evidence.jsonl"
    if not path.is_file():
        return []
    cards: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            card = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(card, dict):
            cards.append(card)
    return cards


def build_research_index(config: Config) -> dict:
    """Build an in-memory bidirectional index across Vault, Zotero manifest, and research/experiments."""
    program = load_research_program(config)
    manifest_items = load_manifest(config).get("items", {})
    papers: dict[str, dict] = {}
    corpus_by_zkey = {
        str(entry.get("zotero_item_key")): entry
        for entry in program.corpus
        if entry.get("zotero_item_key")
    }
    corpus_by_id = {str(entry.get("id")): entry for entry in program.corpus if entry.get("id")}

    def ensure_paper(citekey: str) -> dict:
        if citekey not in papers:
            papers[citekey] = {
                "citekey": citekey,
                "zotero_key": "",
                "title": "",
                "note_path": "",
                "manual_note_path": "",
                "week": None,
                "priority": "",
                "rq_ids": [],
                "hypothesis_ids": [],
                "experiment_ids": [],
                "baseline_for": [],
                "challenged_by_experiments": [],
                "research_roles": [],
                "novelty_threats": [],
                "positioning_paths": [],
                "question_paths": [],
                "evidence_count": 0,
                "evidence_cards": [],
                "search_text": "",
            }
        return papers[citekey]

    for zkey, record in manifest_items.items():
        citekey = record.get("citekey") or zkey
        entry = ensure_paper(citekey)
        entry["zotero_key"] = zkey
        entry["note_path"] = record.get("note_path", "")
        note_file = config.vault / entry["note_path"] if entry["note_path"] else None
        if note_file and note_file.is_file():
            raw = note_file.read_text(encoding="utf-8")
            fm, body = _split_frontmatter(raw)
            entry["title"] = str(fm.get("title") or entry["title"])
            entry["search_text"] += "\n" + raw
            rqs, hyps, exps, _ = _extract_links(raw)
            entry["rq_ids"].extend(rqs)
            entry["hypothesis_ids"].extend(hyps)
            entry["experiment_ids"].extend(exps)
        cards = _load_evidence_cards(config, zkey)
        entry["evidence_cards"] = cards
        entry["evidence_count"] = len(cards)
        if cards:
            entry["search_text"] += "\n" + "\n".join(
                f"{c.get('id', '')} p.{c.get('page', '')} {c.get('claim', '')} {c.get('evidence_quote', '')}"
                for c in cards
            )
        if zkey in corpus_by_zkey:
            c = corpus_by_zkey[zkey]
            entry["week"] = c.get("week")
            entry["priority"] = c.get("priority", "")
            entry["title"] = entry["title"] or c.get("title", "")
            if c.get("research_question_id"):
                entry["rq_ids"].append(c["research_question_id"])
            entry["search_text"] += f"\n{c.get('focus', '')} {c.get('collection', '')}"

    for c in program.corpus:
        cid = str(c.get("citation_key") or c.get("id") or c.get("zotero_item_key") or "").strip()
        if not cid:
            continue
        existing = next(
            (p for p in papers.values() if p["zotero_key"] and p["zotero_key"] == c.get("zotero_item_key")),
            None,
        )
        entry = existing or ensure_paper(cid)
        entry["zotero_key"] = entry["zotero_key"] or str(c.get("zotero_item_key") or "")
        entry["title"] = entry["title"] or str(c.get("title") or "")
        entry["week"] = entry["week"] if entry["week"] is not None else c.get("week")
        entry["priority"] = entry["priority"] or str(c.get("priority") or "")
        if c.get("research_question_id"):
            entry["rq_ids"].append(c["research_question_id"])
        entry["search_text"] += f"\n{c.get('title', '')} {c.get('focus', '')} {c.get('collection', '')}"

    for hint in program.manual_notes:
        target_key = hint.get("synced_citekey") or hint.get("corpus_id") or hint["stem"]
        entry = ensure_paper(target_key)
        entry["manual_note_path"] = hint["path"]
        entry["zotero_key"] = entry["zotero_key"] or hint.get("zotero_key", "")
        raw = (config.vault / hint["path"]).read_text(encoding="utf-8")
        entry["search_text"] += "\n" + raw
        if not entry["title"]:
            heading = HEADING_RE.search(raw)
            if heading:
                entry["title"] = heading.group(1)

    positioning_cards: list[dict] = []
    novelty_ledgers: list[dict] = []
    synthesis_dir = config.vault / "03-Synthesis"
    if synthesis_dir.is_dir():
        for path in sorted(synthesis_dir.glob("*.md")):
            raw = path.read_text(encoding="utf-8")
            fm, body = _split_frontmatter(raw)
            rqs, hyps, exps, wikilinks = _extract_links(raw)
            rqs = list(dict.fromkeys([*_as_str_list(fm.get("rq_ids")), *rqs]))
            hyps = list(dict.fromkeys([*_as_str_list(fm.get("hypothesis_ids")), *hyps]))
            exps = list(dict.fromkeys([*_as_str_list(fm.get("experiment_ids")), *exps]))
            rel = path.relative_to(config.vault).as_posix()
            kind = fm.get("type")
            if kind == "positioning":
                ck = str(fm.get("citekey") or "").strip()
                baseline_for = _as_str_list(fm.get("baseline_for"))
                challenged_by = _as_str_list(fm.get("challenged_by_experiments"))
                record = {
                    "path": rel,
                    "citekey": ck,
                    "zotero_key": str(fm.get("zotero_key") or ""),
                    "research_role": str(fm.get("research_role") or ""),
                    "novelty_threat": str(fm.get("novelty_threat") or ""),
                    "reading_goal": str(fm.get("reading_goal") or ""),
                    "target_contributions": _as_str_list(fm.get("target_contributions")),
                    "rq_ids": rqs,
                    "hypothesis_ids": hyps,
                    "experiment_ids": list(dict.fromkeys([*exps, *baseline_for, *challenged_by])),
                    "baseline_for": baseline_for,
                    "challenged_by_experiments": challenged_by,
                    "body": body,
                }
                positioning_cards.append(record)
                if ck:
                    p = ensure_paper(ck)
                    p["positioning_paths"].append(rel)
                    if record["research_role"]:
                        p["research_roles"].append(record["research_role"])
                    if record["novelty_threat"]:
                        p["novelty_threats"].append(record["novelty_threat"])
                    p["rq_ids"].extend(rqs)
                    p["hypothesis_ids"].extend(hyps)
                    p["experiment_ids"].extend(record["experiment_ids"])
                    p["baseline_for"].extend(baseline_for)
                    p["challenged_by_experiments"].extend(challenged_by)
                    p["search_text"] += "\n" + raw
            elif kind == "novelty-ledger":
                novelty_ledgers.append(
                    {
                        "path": rel,
                        "title": str(fm.get("title") or path.stem),
                        "status": str(fm.get("status") or ""),
                        "rq_ids": rqs,
                        "hypothesis_ids": hyps,
                        "experiment_ids": exps,
                        "paper_citekeys": wikilinks,
                        "rows": _parse_markdown_tables(body),
                        "body": body,
                    }
                )

    questions: list[dict] = []
    questions_dir = config.vault / "04-Questions"
    if questions_dir.is_dir():
        for path in sorted(questions_dir.glob("*.md")):
            raw = path.read_text(encoding="utf-8")
            fm, body = _split_frontmatter(raw)
            heading = HEADING_RE.search(body)
            rqs, hyps, exps, wikilinks = _extract_links(raw)
            rqs = list(dict.fromkeys([*_as_str_list(fm.get("rq_ids")), *rqs]))
            hyps = list(dict.fromkeys([*_as_str_list(fm.get("hypothesis_ids")), *hyps]))
            exps = list(dict.fromkeys([*_as_str_list(fm.get("experiment_ids")), *exps]))
            rel = path.relative_to(config.vault).as_posix()
            questions.append(
                {
                    "path": rel,
                    "title": str(fm.get("title") or (heading.group(1) if heading else path.stem)),
                    "status": str(fm.get("status") or "open"),
                    "question_kind": str(fm.get("question_kind") or "scientific"),
                    "rq_ids": rqs,
                    "hypothesis_ids": hyps,
                    "experiment_ids": exps,
                    "paper_citekeys": wikilinks,
                    "body": body,
                }
            )
            for ck in wikilinks:
                if ck in papers or ck in corpus_by_id:
                    p = ensure_paper(ck)
                    p["question_paths"].append(rel)
                    p["rq_ids"].extend(rqs)
                    p["hypothesis_ids"].extend(hyps)
                    p["experiment_ids"].extend(exps)

    experiments_by_id: dict[str, dict] = {}
    for row in program.ledger_experiments:
        experiments_by_id[row["id"]] = {
            "id": row["id"],
            "title": row["label"],
            "status": row["status_result"],
            "path": (
                (program.research_dir / "EXPERIMENT_LEDGER.md").as_posix()
                if program.research_dir
                else ""
            ),
            "rq_ids": list(row["rq_ids"]),
            "hypothesis_ids": list(row["hypothesis_ids"]),
            "paper_citekeys": list(row["paper_citekeys"]),
            "baseline_papers": [],
            "inspired_by": [],
            "challenged_papers": [],
            "failure_modes": [],
            "body": " | ".join(filter(None, [row["design"], row["status_result"], row["next_step"]])),
        }
    for rep in program.experiment_reports:
        existing = experiments_by_id.get(rep["id"], {})
        merged = {
            **rep,
            "rq_ids": list(dict.fromkeys([*existing.get("rq_ids", []), *rep["rq_ids"]])),
            "hypothesis_ids": list(
                dict.fromkeys([*existing.get("hypothesis_ids", []), *rep["hypothesis_ids"]])
            ),
            "paper_citekeys": list(
                dict.fromkeys(
                    [
                        *existing.get("paper_citekeys", []),
                        *rep["paper_citekeys"],
                        *rep["baseline_papers"],
                        *rep["inspired_by"],
                        *rep["challenged_papers"],
                    ]
                )
            ),
        }
        experiments_by_id[rep["id"]] = merged

    for exp in experiments_by_id.values():
        for ck in exp["paper_citekeys"]:
            p = ensure_paper(ck)
            p["experiment_ids"].append(exp["id"])
            p["rq_ids"].extend(exp["rq_ids"])
            p["hypothesis_ids"].extend(exp["hypothesis_ids"])
        for ck in exp.get("baseline_papers", []):
            ensure_paper(ck)["baseline_for"].append(exp["id"])
        for ck in exp.get("challenged_papers", []):
            ensure_paper(ck)["challenged_by_experiments"].append(exp["id"])

    for p in papers.values():
        for field_name in (
            "rq_ids",
            "hypothesis_ids",
            "experiment_ids",
            "baseline_for",
            "challenged_by_experiments",
            "research_roles",
            "novelty_threats",
            "positioning_paths",
            "question_paths",
        ):
            p[field_name] = list(dict.fromkeys(p[field_name]))

    return {
        "program": program,
        "papers": papers,
        "positioning_cards": positioning_cards,
        "novelty_ledgers": novelty_ledgers,
        "questions": questions,
        "experiments": list(experiments_by_id.values()),
    }


def _matches(query: str, *texts: object) -> bool:
    needle = query.strip().casefold()
    if not needle:
        return True
    haystack = "\n".join(str(item or "") for item in texts).casefold()
    if needle in haystack:
        return True
    tokens = [token for token in re.split(r"\s+", needle) if len(token) >= 2]
    return bool(tokens) and all(token in haystack for token in tokens)


def query_research(config: Config, query: str, *, kind: str = "all") -> dict:
    """Query papers, RQs, hypotheses, positioning/competitors, evidence, and experiments."""
    index = build_research_index(config)
    program: ResearchProgramSummary = index["program"]
    q_norm = query.strip()
    q_upper = q_norm.upper()

    matched_papers: list[dict] = []
    matched_evidence: list[dict] = []
    matched_positioning: list[dict] = []
    matched_ledgers: list[dict] = []
    matched_questions: list[dict] = []
    matched_rqs: list[dict] = []
    matched_hypotheses: list[dict] = []
    matched_experiments: list[dict] = []

    if kind in ("all", "rq"):
        for rq in program.rqs:
            if _matches(q_norm, rq["id"], rq["question"], rq["required_reading"], rq["optional_reading"]):
                matched_rqs.append(rq)

    if kind in ("all", "hypothesis"):
        for hyp in program.hypotheses:
            if _matches(
                q_norm,
                hyp["id"],
                hyp["source"],
                hyp["statement"],
                hyp["falsification"],
                hyp["evidence"],
            ):
                matched_hypotheses.append(hyp)

    if kind in ("all", "experiment"):
        for exp in index["experiments"]:
            if _matches(
                q_norm,
                exp["id"],
                exp["title"],
                exp["status"],
                " ".join(exp["rq_ids"]),
                " ".join(exp["hypothesis_ids"]),
                " ".join(exp["paper_citekeys"]),
                " ".join(exp["failure_modes"]),
                exp["body"],
            ):
                matched_experiments.append(exp)

    if kind in ("all", "competitor", "paper"):
        for card in index["positioning_cards"]:
            is_competitor_query = kind == "competitor" and card["research_role"] in (
                "direct_competitor",
                "baseline",
            )
            if (is_competitor_query and not q_norm) or _matches(
                q_norm,
                card["citekey"],
                card["research_role"],
                card["novelty_threat"],
                " ".join(card["target_contributions"]),
                " ".join(card["rq_ids"]),
                " ".join(card["hypothesis_ids"]),
                " ".join(card["experiment_ids"]),
                card["body"],
            ):
                if kind != "competitor" or card["research_role"] in (
                    "direct_competitor",
                    "baseline",
                    "component",
                ):
                    matched_positioning.append(card)
        for ledger in index["novelty_ledgers"]:
            if _matches(
                q_norm,
                ledger["title"],
                " ".join(ledger["rq_ids"]),
                " ".join(ledger["hypothesis_ids"]),
                " ".join(ledger["paper_citekeys"]),
                ledger["body"],
            ):
                matched_ledgers.append(ledger)

    if kind in ("all", "paper", "rq", "hypothesis", "experiment", "competitor"):
        for paper in index["papers"].values():
            direct_id_match = (
                q_upper in [v.upper() for v in paper["rq_ids"]]
                or q_upper in [v.upper() for v in paper["hypothesis_ids"]]
                or q_upper in [v.upper() for v in paper["experiment_ids"]]
                or q_norm.casefold() in (paper["citekey"].casefold(), paper["zotero_key"].casefold())
            )
            if direct_id_match or _matches(
                q_norm,
                paper["citekey"],
                paper["zotero_key"],
                paper["title"],
                " ".join(paper["rq_ids"]),
                " ".join(paper["hypothesis_ids"]),
                " ".join(paper["experiment_ids"]),
                " ".join(paper["research_roles"]),
                paper["search_text"],
            ):
                if kind == "competitor" and not any(
                    r in ("direct_competitor", "baseline") for r in paper["research_roles"]
                ):
                    continue
                matched_papers.append(
                    {k: v for k, v in paper.items() if k not in ("search_text", "evidence_cards")}
                )

    if kind in ("all", "evidence", "paper", "hypothesis"):
        for paper in index["papers"].values():
            for card in paper["evidence_cards"]:
                if _matches(
                    q_norm,
                    paper["citekey"],
                    paper["zotero_key"],
                    card.get("id"),
                    card.get("type"),
                    card.get("claim"),
                    card.get("evidence_quote"),
                    " ".join(paper["hypothesis_ids"]),
                ):
                    matched_evidence.append(
                        {
                            "citekey": paper["citekey"],
                            "zotero_key": paper["zotero_key"],
                            "id": card.get("id"),
                            "page": card.get("page"),
                            "type": card.get("type"),
                            "claim": card.get("claim"),
                            "evidence_quote": card.get("evidence_quote"),
                            "source_chunk": card.get("source_chunk"),
                        }
                    )

    if kind in ("all", "rq", "hypothesis", "experiment"):
        for question in index["questions"]:
            if _matches(
                q_norm,
                question["title"],
                " ".join(question["rq_ids"]),
                " ".join(question["hypothesis_ids"]),
                " ".join(question["experiment_ids"]),
                " ".join(question["paper_citekeys"]),
                question["body"],
            ):
                matched_questions.append({k: v for k, v in question.items() if k != "body"})

    return {
        "query": q_norm,
        "kind": kind,
        "papers": matched_papers,
        "evidence": matched_evidence,
        "positioning": [{k: v for k, v in c.items() if k != "body"} for c in matched_positioning],
        "novelty_ledgers": [{k: v for k, v in ledger.items() if k != "body"} for ledger in matched_ledgers],
        "questions": matched_questions,
        "rqs": matched_rqs,
        "hypotheses": matched_hypotheses,
        "experiments": [{k: v for k, v in exp.items() if k != "body"} for exp in matched_experiments],
    }
