"""Check provenance for researcher interpretation stored outside Literature."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

import yaml

from .config import Config
from .triage import FRONTMATTER, NOVELTY_THREATS, READING_GOALS, RESEARCH_ROLES


def validate_positioning(config: Config, plan: dict, state: dict, cards: list[dict]) -> Path | None:
    """Validate the declared card, without claiming to validate its interpretation."""
    relative = Path(plan["positioning_path"])
    root = (config.vault / "03-Synthesis").resolve()
    path = (config.vault / relative).resolve()
    if relative.is_absolute() or not path.is_relative_to(root) or path.suffix != ".md":
        raise ValueError("positioning_path must point to a Markdown note inside 03-Synthesis/")
    if not path.is_file():
        return None
    content = path.read_text(encoding="utf-8")
    match = FRONTMATTER.match(content)
    try:
        metadata = yaml.safe_load(match.group(1)) if match else None
    except yaml.YAMLError as error:
        raise ValueError(f"Positioning card has invalid YAML: {error}") from error
    if not isinstance(metadata, dict) or metadata.get("type") != "positioning":
        raise ValueError("Positioning card needs frontmatter with type: positioning")
    for key in ("citekey", "zotero_key", "source_sha256"):
        if metadata.get(key) != state[key]:
            raise ValueError(f"Positioning card {key} does not match the current paper source")
    evidence_path = config.state_dir / "papers" / state["zotero_key"] / "evidence.jsonl"
    evidence_hash = hashlib.sha256(evidence_path.read_bytes()).hexdigest()
    if metadata.get("evidence_sha256") != evidence_hash:
        raise ValueError("Positioning card evidence_sha256 does not match current validated evidence")
    if metadata.get("inference") is not True:
        raise ValueError("Positioning card must label researcher interpretation with inference: true")
    for key, allowed in (
        ("research_role", RESEARCH_ROLES),
        ("novelty_threat", NOVELTY_THREATS),
        ("reading_goal", READING_GOALS),
    ):
        if metadata.get(key) not in allowed:
            raise ValueError(f"Positioning card has invalid {key}")
    if metadata.get("target_contributions") != plan.get("target_contributions", []):
        raise ValueError("Positioning card target_contributions differ from the reading plan")
    body = re.sub(r"<!--.*?-->", "", content[match.end():], flags=re.DOTALL)
    if f"[[{state['citekey']}]]" not in body:
        raise ValueError("Positioning card needs an exact Literature citekey link")
    referenced = set(re.findall(r"\bE\d{3,}\b", body))
    known = {card["id"] for card in cards}
    if not referenced or referenced - known:
        raise ValueError("Positioning card needs valid evidence IDs from this paper")
    return path
