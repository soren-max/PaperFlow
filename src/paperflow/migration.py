"""Capture legacy knowledge ownership and reconcile one paper at a time."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path

import yaml

from .config import Config, load_manifest
from .ingest import _hash_file, _write_json, resolve_paper
from .process import inspect

LEGACY_FOLDERS = {
    "02-Concepts": "concept",
    "03-Synthesis": "synthesis",
    "04-Questions": "question",
}
MY_NOTES = "## My Notes"


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _read_note(path: Path) -> tuple[str, str]:
    content = path.read_text(encoding="utf-8")
    markers = list(re.finditer(rf"(?m)^{re.escape(MY_NOTES)}\s*$", content))
    if len(markers) != 1:
        raise ValueError(f"{path} must have exactly one ## My Notes boundary")
    return content, content[markers[0].start() :]


def _title(content: str) -> str:
    match = re.match(r"\A---\s*\n(.*?)\n---\s*\n", content, flags=re.DOTALL)
    if not match:
        return ""
    try:
        frontmatter = yaml.safe_load(match.group(1))
    except yaml.YAMLError as error:
        raise ValueError("Invalid Literature frontmatter") from error
    return frontmatter.get("title", "") if isinstance(frontmatter, dict) else ""


def _legacy_assets(config: Config, citekey: str) -> list[dict]:
    link = f"[[{citekey}]]"
    assets = []
    for folder, kind in LEGACY_FOLDERS.items():
        root = config.vault / folder
        if not root.is_dir():
            continue
        for path in root.rglob("*.md"):
            content = path.read_text(encoding="utf-8")
            if link in content:
                assets.append(
                    {
                        "path": path.relative_to(config.vault).as_posix(),
                        "kind": kind,
                        "sha256": _digest(content),
                    }
                )
    return sorted(assets, key=lambda asset: asset["path"])


def _duplicate_candidates(config: Config, key: str, title: str) -> list[dict]:
    candidates = []
    for other_key, other in load_manifest(config).get("items", {}).items():
        if other_key == key:
            continue
        other_path = config.vault / other["note_path"]
        if not other_path.is_file():
            continue
        try:
            other_title = _title(other_path.read_text(encoding="utf-8"))
        except ValueError:
            continue
        if other_title == title:
            candidates.append(
                {
                    "zotero_key": other_key,
                    "citekey": other["citekey"],
                    "note_path": other["note_path"],
                }
            )
    return candidates


def capture(config: Config, paper: str) -> tuple[Path, dict, bool]:
    """Create an immutable baseline for a single synced Zotero item."""
    key, record = resolve_paper(config, paper)
    directory = config.state_dir / "migrations" / key
    path = directory / "migration.json"
    if path.is_file():
        return directory, json.loads(path.read_text(encoding="utf-8")), False
    note_path = config.vault / record["note_path"]
    content, my_notes = _read_note(note_path)
    title = _title(content)
    if not title:
        raise ValueError(f"{note_path} lacks a Literature title in frontmatter")
    baseline = {
        "schema_version": 1,
        "captured_at": datetime.now(UTC).isoformat(),
        "identity": {
            "zotero_key": key,
            "citekey": record["citekey"],
            "note_path": record["note_path"],
            "title": title,
        },
        "legacy": {
            "my_notes_sha256": _digest(my_notes),
            "my_notes_characters": len(my_notes),
            "v2_present_at_capture": "<!-- paperflow:v2 begin -->" in content,
            "assets": _legacy_assets(config, record["citekey"]),
            "duplicate_candidates": _duplicate_candidates(config, key, title),
        },
        "manual_review": {"decision_file": "migration-review.md", "decision": "pending"},
    }
    directory.mkdir(parents=True, exist_ok=True)
    _write_json(path, baseline)
    return directory, baseline, True


def reconcile(config: Config, paper: str) -> tuple[Path, dict]:
    """Read current state; never update the captured legacy baseline or knowledge notes."""
    directory, baseline, _ = capture(config, paper)
    identity = baseline["identity"]
    key = identity["zotero_key"]
    issues = []
    current_record = load_manifest(config).get("items", {}).get(key, {})
    if (
        current_record.get("citekey") != identity["citekey"]
        or current_record.get("note_path") != identity["note_path"]
    ):
        issues.append("Sync manifest identity differs from legacy capture")
    note_path = config.vault / identity["note_path"]
    my_notes_preserved = False
    try:
        content, my_notes = _read_note(note_path)
        my_notes_preserved = _digest(my_notes) == baseline["legacy"]["my_notes_sha256"]
        if not my_notes_preserved:
            issues.append("My Notes changed since legacy capture")
        if _title(content) != identity["title"]:
            issues.append("Literature title changed since legacy capture; check Zotero identity")
    except (OSError, ValueError) as error:
        issues.append(str(error))
    changed_assets = []
    baseline_paths = {asset["path"] for asset in baseline["legacy"]["assets"]}
    for asset in baseline["legacy"]["assets"]:
        path = config.vault / asset["path"]
        if not path.is_file() or _digest(path.read_text(encoding="utf-8")) != asset["sha256"]:
            changed_assets.append(asset["path"])
    if changed_assets:
        issues.append("Legacy knowledge assets changed since capture")
    new_assets = [
        asset["path"]
        for asset in _legacy_assets(config, identity["citekey"])
        if asset["path"] not in baseline_paths
    ]
    if new_assets:
        issues.append("New linked knowledge assets appeared since capture")
    paper_dir = config.state_dir / "papers" / key
    stages = {}
    if paper_dir.is_dir():
        try:
            source_state = json.loads((paper_dir / "state.json").read_text(encoding="utf-8"))
            if any(
                source_state.get(field) != expected
                for field, expected in (
                    ("zotero_key", key),
                    ("citekey", identity["citekey"]),
                    ("note_path", identity["note_path"]),
                )
            ):
                issues.append("Pipeline identity differs from legacy capture")
            pdf = Path(source_state["pdf_locator"])
            if not pdf.is_file() or _hash_file(pdf) != source_state.get("pdf_sha256"):
                issues.append("Zotero PDF locator is missing or its contents changed")
            _, state, pipeline_issues = inspect(config, key)
            stages = state["stages"]
            issues.extend(pipeline_issues)
        except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
            issues.append(f"Pipeline provenance: {error}")
    review_path = directory / baseline["manual_review"]["decision_file"]
    review_text = review_path.read_text(encoding="utf-8") if review_path.is_file() else ""
    decision = re.search(r"(?m)^Decision: (pending|accepted|rejected)$", review_text)
    review_decision = decision.group(1) if decision else "pending"
    pipeline_done = (
        stages.get("literature_published") == "done"
        and stages.get("knowledge_integrated") == "done"
    )
    if issues:
        status = "conflict"
    elif not pipeline_done:
        status = "pipeline_pending"
    elif review_decision == "accepted":
        status = "migrated"
    elif review_decision == "rejected":
        status = "rejected"
    else:
        status = "review_required"
    result = {
        "schema_version": 1,
        "checked_at": datetime.now(UTC).isoformat(),
        "zotero_key": key,
        "citekey": identity["citekey"],
        "status": status,
        "pipeline_stages": stages,
        "my_notes_preserved": my_notes_preserved,
        "changed_legacy_assets": changed_assets,
        "new_legacy_assets": new_assets,
        "duplicate_candidates": _duplicate_candidates(config, key, identity["title"]),
        "manual_review_decision": review_decision,
        "issues": issues,
    }
    _write_json(directory / "reconcile.json", result)
    return directory, result
