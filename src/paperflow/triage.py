"""Triage a synced paper: bounded metadata in, one routing card out.

Triage decides whether a paper deserves deep processing. It never reads the PDF:
the Literature note already holds the source-grounded metadata, abstract, and
annotations, so the backlog can be triaged offline without an ingest step.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import yaml

from .config import Config, load_manifest
from .ingest import _write_json, resolve_paper
from .markdown import ANNOTATIONS_BEGIN, ANNOTATIONS_END, METADATA_BEGIN, METADATA_END

PACKET_NAME = "packet.md"
CARD_NAME = "paper-card.md"
AREAS_DIR = "00-Research-Areas"
QUESTIONS_DIR = "04-Questions"
ABSTRACT_BUDGET = 4_000
CONTEXT_BUDGET = 20_000
CONTEXT_ENTRIES = 300
SECTION_WORD_LIMIT = 80
FRONTMATTER_HEAD = 8_192
PRIORITIES = ("low", "medium", "high")
RECOMMENDATIONS = ("yes", "no")
BASIS_TOKENS = ("abstract", "title", "tags", "annotations", "venue", "sections")
CARD_SECTIONS = ("Problem", "Method", "Dataset", "Potential relevance", "Basis")

FRONTMATTER = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n", re.DOTALL)
HEADING = re.compile(r"(?m)^#\s+(.+?)\s*$")
ABSTRACT_HEADING = re.compile(r"(?m)^##\s+Abstract\s*$")
SECTION = re.compile(r"(?m)^##\s+(.+?)\s*$")
NO_ABSTRACT = "_No abstract in Zotero._"


@dataclass
class TriageRow:
    citekey: str
    zotero_key: str
    status: str
    research_area: str = ""
    priority: str = ""
    deep_processing: str = ""
    issues: list[str] = field(default_factory=list)


@dataclass
class TriageResult:
    rows: list[TriageRow] = field(default_factory=list)
    ready: int = 0
    valid: int = 0
    high: int = 0
    recommended: int = 0
    remaining: int = 0
    missing_notes: list[str] = field(default_factory=list)


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _bounded_block(text: str, begin: str, end: str, label: str) -> str:
    match = re.search(re.escape(begin) + r"(.*?)" + re.escape(end), text, re.DOTALL)
    if match is None:
        raise ValueError(f"{label} is missing. Run paperflow sync for this paper first.")
    return match.group(1).strip("\n")


def _field(block: str, name: str) -> str:
    match = re.search(rf"(?m)^>\s+\*\*{re.escape(name)}:\*\*\s*(.*?)\s*$", block)
    return match.group(1).strip() if match else ""


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    match = FRONTMATTER.match(text)
    if match is None:
        raise ValueError("Literature note has no YAML frontmatter. Run paperflow sync first.")
    try:
        data = yaml.safe_load(match.group(1))
    except yaml.YAMLError as error:
        raise ValueError(f"Literature note frontmatter is unreadable: {error}") from error
    return (data if isinstance(data, dict) else {}), match.group(1).strip()


def _parse_note(text: str) -> dict:
    frontmatter, frontmatter_text = _parse_frontmatter(text)
    metadata = _bounded_block(text, METADATA_BEGIN, METADATA_END, "Managed metadata block")
    annotations = _bounded_block(text, ANNOTATIONS_BEGIN, ANNOTATIONS_END, "Managed annotations")
    title = HEADING.search(metadata)
    abstract_match = ABSTRACT_HEADING.search(metadata)
    abstract = metadata[abstract_match.end() :].strip() if abstract_match else ""
    if abstract == NO_ABSTRACT:
        abstract = ""
    return {
        "frontmatter": frontmatter_text,
        "title": frontmatter.get("title") or (title.group(1) if title else "Untitled"),
        "authors": _field(metadata, "Authors"),
        "year": _field(metadata, "Year"),
        "venue": _field(metadata, "Venue"),
        "doi": frontmatter.get("doi") or "",
        "tags": frontmatter.get("tags") or [],
        "abstract": abstract,
        "annotations": annotations,
    }


def _shortened(value: str, budget: int) -> str:
    if len(value) <= budget:
        return value
    return value[:budget].rstrip() + f"\n\n[… truncated at {budget} characters]"


def _head(path: Path) -> tuple[dict, str]:
    """Read only the head of a note; fall back to the whole file for long frontmatter."""
    with path.open(encoding="utf-8") as handle:
        head = handle.read(FRONTMATTER_HEAD)
        if not (match := FRONTMATTER.match(head)):
            head = handle.read()
            match = FRONTMATTER.match(head)
    if match is None:
        return {}, head
    try:
        data = yaml.safe_load(match.group(1))
    except yaml.YAMLError:
        return {}, head[match.end() :]
    return (data if isinstance(data, dict) else {}), head[match.end() :]


def _digest_line(path: Path, vault: Path, extra: str = "") -> str:
    frontmatter, body = _head(path)
    heading = HEADING.search(body)
    title = frontmatter.get("title") or (heading.group(1) if heading else path.stem)
    tags = frontmatter.get("tags") or []
    suffix = f" — tags: {', '.join(str(tag) for tag in tags)}" if tags else ""
    return f"- `{path.relative_to(vault).as_posix()}` — {title}{suffix}{extra}"


def context_digest(config: Config) -> str:
    """Describe the vault's current research context within a fixed budget."""
    sections = [
        ("Research Areas", config.vault / AREAS_DIR),
        ("Open Questions", config.vault / QUESTIONS_DIR),
    ]
    lines: list[str] = []
    for label, directory in sections:
        paths = sorted(directory.glob("*.md")) if directory.is_dir() else []
        lines.append(f"### {label}")
        if not paths:
            lines.append(f"_None yet. Add notes to `{directory.name}/` to steer triage._")
        lines.extend(_digest_line(path, config.vault) for path in paths)
        lines.append("")

    records = load_manifest(config).get("items", {})
    ordered = sorted(records.items(), key=lambda item: item[1].get("citekey") or "")
    lines.append("### Existing Literature")
    omitted = 0
    for index, (_key, record) in enumerate(ordered):
        if index >= CONTEXT_ENTRIES:
            omitted = len(ordered) - index
            break
        note_path = config.vault / record.get("note_path", "")
        entry = f"- `{record.get('citekey', '?')}`"
        if note_path.is_file():
            frontmatter, body = _head(note_path)
            heading = HEADING.search(body)
            title = frontmatter.get("title") or (heading.group(1) if heading else "")
            tags = frontmatter.get("tags") or []
            entry += f" — {title}" if title else ""
            entry += f" — tags: {', '.join(str(tag) for tag in tags)}" if tags else ""
        if len("\n".join([*lines, entry])) > CONTEXT_BUDGET:
            omitted = len(ordered) - index
            break
        lines.append(entry)
    if omitted:
        lines.append(f"… {omitted} further Literature notes omitted from this digest.")
    return _shortened("\n".join(lines), CONTEXT_BUDGET)


def _section_titles(config: Config, key: str) -> list[str] | None:
    structure = config.state_dir / "papers" / key / "structure.json"
    if not structure.is_file():
        return None
    try:
        entries = json.loads(structure.read_text(encoding="utf-8"))["sections"]
    except (json.JSONDecodeError, KeyError, TypeError) as error:
        raise ValueError(f"{structure} is unreadable: {error}") from error
    return [f"{entry['id']}  {entry['title']}" for entry in entries]


def prepare_packet(config: Config, key: str, record: dict, context: str) -> str:
    """Build the bounded triage input for one paper and return its text."""
    note_path = config.vault / record.get("note_path", "")
    if not note_path.is_file():
        raise ValueError(f"Literature note is missing: {record.get('note_path')}")
    raw = note_path.read_text(encoding="utf-8")
    note = _parse_note(raw)
    titles = _section_titles(config, key)
    blocks = [
        "# Triage packet",
        "",
        f"- citekey: `{record.get('citekey')}`",
        f"- zotero_key: `{key}`",
        f"- note: `{record.get('note_path')}`",
        "",
        "## Paper Metadata",
        "",
        "```yaml",
        note["frontmatter"],
        "```",
        "",
        f"- Title: {note['title']}",
        f"- Authors: {note['authors'] or 'Unknown'}",
        f"- Year: {note['year'] or 'Unknown'}",
        f"- Venue: {note['venue'] or 'unavailable'}",
        f"- DOI: {note['doi'] or 'unavailable'}",
        f"- Tags: {', '.join(str(tag) for tag in note['tags']) or 'none'}",
        "",
        "## Abstract",
        "",
        _shortened(note["abstract"], ABSTRACT_BUDGET) if note["abstract"] else "unavailable",
        "",
        "## Annotations",
        "",
        note["annotations"].strip() or "_No PDF annotations in Zotero._",
        "",
        "## Section Titles",
        "",
        "\n".join(titles) if titles else "unavailable (paper is not ingested yet)",
        "",
        "## Research Context",
        "",
        context,
        "",
        "## Reading Boundary",
        "",
        "This packet contains metadata, the abstract, Zotero annotations, and section titles only.",
        "No PDF text is included, so no section-level evidence or result can be quoted from it.",
        "Record `unsupported` rather than guessing when a required field is not stated here.",
        "",
    ]
    return "\n".join(blocks)


def _split_sections(text: str) -> dict[str, str]:
    matches = list(SECTION.finditer(text))
    sections: dict[str, str] = {}
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        sections[match.group(1).strip()] = text[match.end() : end].strip()
    return sections


def _basis_tokens(value: object) -> list[str]:
    if isinstance(value, list):
        parts = [str(part) for part in value]
    elif isinstance(value, str):
        parts = re.split(r"[,\s]+", value)
    else:
        return []
    return [part.strip().casefold() for part in parts if part.strip()]


def _scalar(value: object) -> object:
    """YAML reads bare `yes`/`no` as booleans; keep the card contract readable."""
    return ("yes" if value else "no") if isinstance(value, bool) else value


def validate_card(path: Path, state: dict) -> tuple[list[str], dict]:
    """Check one paper-card.md against the deterministic contract."""
    issues: list[str] = []
    text = path.read_text(encoding="utf-8")
    try:
        frontmatter, _ = _parse_frontmatter(text)
    except ValueError as error:
        return [str(error)], {}
    if frontmatter.get("paperflow_card") != 1:
        issues.append("paper-card.md needs `paperflow_card: 1` in its frontmatter")
    for field_name in ("citekey", "zotero_key", "research_area", "priority"):
        value = _scalar(frontmatter.get(field_name))
        if not isinstance(value, str) or not value.strip():
            issues.append(f"paper-card.md: missing {field_name}")
    if frontmatter.get("citekey") != state.get("citekey"):
        issues.append(f"paper-card.md: citekey does not match {state.get('citekey')}")
    if frontmatter.get("zotero_key") != state.get("zotero_key"):
        issues.append(f"paper-card.md: zotero_key does not match {state.get('zotero_key')}")
    priority = _scalar(frontmatter.get("priority"))
    if isinstance(priority, str) and priority.strip() and priority not in PRIORITIES:
        issues.append(f"paper-card.md: priority must be one of {', '.join(PRIORITIES)}")
    recommendation = _scalar(frontmatter.get("deep_processing"))
    if not isinstance(recommendation, str) or not recommendation.strip():
        issues.append("paper-card.md: missing deep_processing")
    elif recommendation not in RECOMMENDATIONS:
        issues.append("paper-card.md: deep_processing must be yes or no")
    tokens = _basis_tokens(frontmatter.get("basis"))
    if not tokens:
        issues.append("paper-card.md: basis must name the packet inputs used")
    unknown = [token for token in tokens if token not in BASIS_TOKENS]
    if unknown:
        issues.append(f"paper-card.md: unknown basis entries: {', '.join(sorted(unknown))}")
    if "sections" in tokens and not state.get("sections_available"):
        issues.append("paper-card.md: section titles were not in this packet")
    sections = _split_sections(text)
    for name in CARD_SECTIONS:
        content = sections.get(name)
        if not content:
            issues.append(f"paper-card.md: missing an empty `## {name}` section")
            continue
        words = len(content.split())
        if words > SECTION_WORD_LIMIT:
            issues.append(
                f"paper-card.md: `## {name}` has {words} words (limit {SECTION_WORD_LIMIT})"
            )
    card = {
        "research_area": _scalar(frontmatter.get("research_area")) or "",
        "priority": priority or "",
        "deep_processing": recommendation or "",
        "basis": tokens,
    }
    return issues, card


def summary(config: Config) -> dict:
    """Count triage progress from state files only, without re-reading Literature notes."""
    records = load_manifest(config).get("items", {})
    root = config.state_dir / "triage"
    prepared = carded = high = recommended = 0
    state_paths = sorted(root.glob("*/state.json")) if root.is_dir() else []
    for state_path in state_paths:
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        prepared += 1
        if not state.get("card") or not (state_path.parent / CARD_NAME).is_file():
            continue
        carded += 1
        high += int(state["card"].get("priority") == "high")
        recommended += int(state["card"].get("deep_processing") == "yes")
    return {
        "prepared": prepared,
        "carded": carded,
        "high": high,
        "recommended": recommended,
        "pending": max(len(records) - carded, 0),
    }


def _needs_triage(config: Config, key: str, record: dict) -> bool:
    """A paper is pending until it has a card for the note it currently has."""
    directory = config.state_dir / "triage" / key
    state_path = directory / "state.json"
    note_path = config.vault / record.get("note_path", "")
    if not note_path.is_file() or not state_path.is_file():
        return True
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return True
    if state.get("note_sha256") != _sha256(note_path.read_text(encoding="utf-8")):
        return True
    return not (directory / CARD_NAME).is_file()


def triage(
    config: Config,
    paper: str | None = None,
    limit: int = 25,
    refresh: bool = False,
) -> TriageResult:
    """Prepare packets, validate cards, and report what still needs triage."""
    records = load_manifest(config).get("items", {})
    if paper is not None:
        key, record = resolve_paper(config, paper)
        entries = [(key, record)]
    else:
        entries = list(records.items())

    def order(entry: tuple[str, dict, bool]) -> tuple[int, str]:
        return (-int(entry[1].get("annotation_count") or 0), entry[1].get("citekey") or "")

    examined = [(key, record, _needs_triage(config, key, record)) for key, record in entries]
    # Papers that still need triage come first, so repeated runs walk the backlog.
    ranked = sorted((entry for entry in examined if entry[2]), key=order) + sorted(
        (entry for entry in examined if not entry[2]), key=order
    )
    result = TriageResult()
    result.remaining = max(sum(entry[2] for entry in examined) - limit, 0)
    candidates = ranked[:limit]
    context: str | None = None
    now = datetime.now(UTC).isoformat()

    for key, record, _needs_work in candidates:
        row = TriageRow(citekey=record.get("citekey") or key, zotero_key=key, status="ready")
        note_path = config.vault / record.get("note_path", "")
        if not note_path.is_file():
            row.status = "missing-note"
            result.missing_notes.append(record.get("note_path") or key)
            result.rows.append(row)
            continue
        directory = config.state_dir / "triage" / key
        directory.mkdir(parents=True, exist_ok=True)
        packet_path = directory / PACKET_NAME
        card_path = directory / CARD_NAME
        state_path = directory / "state.json"
        note_hash = _sha256(note_path.read_text(encoding="utf-8"))
        previous: dict = {}
        if state_path.is_file():
            try:
                previous = json.loads(state_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                previous = {}
        stale = previous.get("note_sha256") != note_hash
        if refresh or stale or not packet_path.is_file():
            if context is None:
                context = context_digest(config)
            packet = prepare_packet(config, key, record, context)
            packet_path.write_text(packet, encoding="utf-8")
            result.ready += 1
        titles = _section_titles(config, key) is not None
        state = {
            "version": 1,
            "zotero_key": key,
            "citekey": record.get("citekey"),
            "note_path": record.get("note_path"),
            "note_sha256": note_hash,
            "packet_sha256": _sha256(packet_path.read_text(encoding="utf-8")),
            "sections_available": titles,
            "prepared_at": now,
            "card": None,
        }
        if card_path.is_file() and not stale:
            issues, card = validate_card(card_path, state)
            row.issues = issues
            row.research_area = card.get("research_area", "")
            row.priority = card.get("priority", "")
            row.deep_processing = card.get("deep_processing", "")
            if issues:
                row.status = "invalid"
            else:
                row.status = "card"
                state["card"] = card
                result.valid += 1
                result.high += int(card["priority"] == "high")
                result.recommended += int(card["deep_processing"] == "yes")
        elif card_path.is_file():
            row.status = "stale"
        result.rows.append(row)
        _write_json(state_path, state)
    return result
