"""Validate staged reading artifacts and resume from durable files."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from .config import Config
from .ingest import _write_json, resolve_paper

EVIDENCE_TYPES = {
    "problem",
    "definition",
    "assumption",
    "method",
    "mechanism",
    "dataset",
    "metric",
    "result",
    "ablation",
    "limitation",
    "author_interpretation",
}
V2_BEGIN = "<!-- paperflow:v2 begin -->"
V2_END = "<!-- paperflow:v2 end -->"


def _read_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object in {path}")
    return value


def _normalized(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _validate_plan(path: Path, valid_ids: set[str]) -> dict | None:
    if not path.is_file():
        return None
    plan = _read_json(path)
    selected = plan.get("reading_sections")
    if (
        not isinstance(selected, list)
        or not selected
        or not all(isinstance(section, str) and section in valid_ids for section in selected)
    ):
        raise ValueError("paper-map.json needs nonempty reading_sections from structure.json")
    if len(selected) != len(set(selected)):
        raise ValueError("paper-map.json has duplicate reading_sections")
    return plan


def _validate_section_evidence(path: Path, section: dict, paper: str) -> list[dict]:
    cards: list[dict] = []
    sources = {
        chunk["path"]: (path.parents[1] / chunk["path"]).read_text(encoding="utf-8")
        for chunk in section["chunks"]
    }
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            card = json.loads(line)
        except json.JSONDecodeError as error:
            raise ValueError(f"{path.name}:{line_number}: invalid JSON") from error
        if not isinstance(card, dict):
            raise ValueError(f"{path.name}:{line_number}: expected an object")
        for field in ("id", "type", "claim", "evidence_quote", "source_chunk"):
            if not isinstance(card.get(field), str) or not card[field].strip():
                raise ValueError(f"{path.name}:{line_number}: missing {field}")
        if card.get("paper") != paper or card.get("section_id") != section["id"]:
            raise ValueError(f"{path.name}:{line_number}: wrong paper or section_id")
        if card["type"] not in EVIDENCE_TYPES:
            raise ValueError(f"{path.name}:{line_number}: unknown evidence type")
        if card["source_chunk"] not in sources:
            raise ValueError(f"{path.name}:{line_number}: unknown source_chunk")
        page = card.get("page")
        if not isinstance(page, int) or not section["page_start"] <= page <= section["page_end"]:
            raise ValueError(f"{path.name}:{line_number}: page outside section")
        source = sources[card["source_chunk"]]
        quote = _normalized(card["evidence_quote"])
        if quote not in _normalized(source):
            raise ValueError(f"{path.name}:{line_number}: evidence_quote not in source_chunk")
        page_parts = re.split(r"(?m)^<!-- page: (\d+) -->\s*$", source)
        quoted_pages = [
            int(page_parts[index])
            for index in range(1, len(page_parts), 2)
            if quote in _normalized(page_parts[index + 1])
        ]
        if page not in quoted_pages:
            raise ValueError(f"{path.name}:{line_number}: quote does not occur on page {page}")
        if card.get("confidence") not in ("high", "medium", "low"):
            raise ValueError(f"{path.name}:{line_number}: invalid confidence")
        cards.append(card)
    return cards


def _validate_refs(path: Path, known_ids: set[str]) -> None:
    content = path.read_text(encoding="utf-8")
    referenced = set(re.findall(r"\bE\d{3,}\b", content))
    if not referenced:
        raise ValueError(f"{path.name} has no evidence card references")
    unknown = referenced - known_ids
    if unknown:
        raise ValueError(f"{path.name} has unknown evidence IDs: {', '.join(sorted(unknown))}")


def inspect(config: Config, paper: str) -> tuple[Path, dict, list[str]]:
    key, _ = resolve_paper(config, paper)
    directory = config.state_dir / "papers" / key
    if not directory.is_dir():
        raise ValueError(f"{paper} is not ingested. Run paperflow ingest {paper}")
    state = _read_json(directory / "state.json")
    structure = _read_json(directory / "structure.json")
    sections = {section["id"]: section for section in structure["sections"]}
    issues: list[str] = []
    source_hash = hashlib.sha256(
        (directory / "source.md").read_text(encoding="utf-8").encode("utf-8")
    ).hexdigest()
    if source_hash != state.get("source_sha256"):
        raise ValueError("source.md changed since ingestion; inspect provenance before processing")
    for entry in structure["sections"]:
        for chunk in entry["chunks"]:
            chunk_path = directory / chunk["path"]
            if not chunk_path.is_file() or hashlib.sha256(
                chunk_path.read_text(encoding="utf-8").encode("utf-8")
            ).hexdigest() != chunk.get("sha256"):
                raise ValueError(f"Source chunk changed or missing: {chunk['path']}")
    try:
        plan = _validate_plan(directory / "paper-map.json", set(sections))
    except ValueError as error:
        issues.append(str(error))
        plan = None
    mapped = (directory / "paper-map.md").is_file() and plan is not None
    state["stages"]["mapped"] = "done" if mapped else "pending"
    cards = []
    selected = plan["reading_sections"] if mapped else []
    for section_id in sections:
        state["sections"][section_id] = (
            "skipped" if mapped and section_id not in selected else "pending"
        )
    for section_id in selected:
        evidence_path = directory / "evidence" / f"{section_id}.jsonl"
        if not evidence_path.is_file():
            continue
        try:
            section_cards = _validate_section_evidence(
                evidence_path, sections[section_id], state["citekey"]
            )
            cards.extend(section_cards)
            state["sections"][section_id] = "done"
        except ValueError as error:
            issues.append(str(error))
            state["sections"][section_id] = "invalid"
    ids = [card["id"] for card in cards]
    if len(ids) != len(set(ids)):
        issues.append("evidence card IDs must be unique across sections")
    if cards and len(ids) == len(set(ids)):
        (directory / "evidence.jsonl").write_text(
            "".join(json.dumps(card, ensure_ascii=False) + "\n" for card in cards), encoding="utf-8"
        )
    evidence_done = bool(selected and cards) and all(
        state["sections"][value] == "done" for value in selected
    )
    state["stages"]["evidence_extracted"] = "done" if evidence_done and not issues else "pending"
    card_paths = [directory / name for name in ("method-card.md", "result-card.md")]
    cards_done = evidence_done and all(path.is_file() for path in card_paths)
    if cards_done:
        for path in card_paths:
            try:
                _validate_refs(path, set(ids))
            except ValueError as error:
                issues.append(str(error))
                cards_done = False
    state["stages"]["cards_built"] = "done" if cards_done else "pending"
    note = directory / "paper-note.md"
    if cards_done and note.is_file():
        try:
            _validate_refs(note, set(ids))
        except ValueError as error:
            issues.append(str(error))
    state["stages"]["paper_synthesized"] = (
        "done" if cards_done and note.is_file() and not issues else "pending"
    )
    literature_path = config.vault / state["note_path"]
    published = False
    if state["stages"]["paper_synthesized"] == "done" and literature_path.is_file():
        literature = literature_path.read_text(encoding="utf-8")
        if V2_BEGIN in literature or V2_END in literature:
            expected = f"{V2_BEGIN}\n{note.read_text(encoding='utf-8').strip()}\n{V2_END}"
            if expected in literature:
                published = True
            else:
                issues.append("Literature V2 block differs from paper-note.md")
    state["stages"]["literature_published"] = "done" if published else "pending"
    state["stages"]["knowledge_integrated"] = (
        "done"
        if published and not issues and (directory / "knowledge-integration.md").is_file()
        else "pending"
    )
    _write_json(directory / "state.json", state)
    return directory, state, issues


def publish_note(config: Config, paper: str) -> Path:
    directory, state, issues = inspect(config, paper)
    if issues or state["stages"]["paper_synthesized"] != "done":
        raise ValueError("Complete and validate evidence, cards, and paper-note.md first")
    note_path = config.vault / state["note_path"]
    original = note_path.read_text(encoding="utf-8")
    content = (directory / "paper-note.md").read_text(encoding="utf-8").strip()
    block = f"{V2_BEGIN}\n{content}\n{V2_END}"
    if V2_BEGIN in original or V2_END in original:
        start = original.find(V2_BEGIN)
        end = original.find(V2_END)
        if start < 0 or end < start:
            raise ValueError("Literature note has an incomplete V2 block")
        old_block = original[start : end + len(V2_END)]
        if old_block != block:
            raise ValueError("Literature V2 block has changed; inspect it before replacing")
        return note_path
    marker = "## My Notes"
    if marker not in original:
        raise ValueError("Literature note lacks ## My Notes; refusing to alter it")
    note_path.write_text(original.replace(marker, f"{block}\n\n{marker}", 1), encoding="utf-8")
    state["stages"]["literature_published"] = "done"
    _write_json(directory / "state.json", state)
    return note_path
