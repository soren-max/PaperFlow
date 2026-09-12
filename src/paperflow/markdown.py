from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from pathlib import Path

import yaml

METADATA_BEGIN = "<!-- paperflow:begin metadata -->"
METADATA_END = "<!-- paperflow:end metadata -->"
ANNOTATIONS_BEGIN = "<!-- paperflow:begin annotations -->"
ANNOTATIONS_END = "<!-- paperflow:end annotations -->"


def _year(value: str) -> str:
    match = re.search(r"\b(1[5-9]\d{2}|20\d{2}|21\d{2})\b", value or "")
    return match.group(0) if match else ""


def _word_slug(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "", ascii_text.lower())


def choose_citekey(item: dict, existing: str | None = None) -> str:
    if existing:
        return existing
    supplied = re.sub(r"[^A-Za-z0-9._-]+", "", item.get("citekey") or "")
    if supplied:
        return supplied
    authors = item.get("authors") or []
    family = _word_slug(authors[0].split()[-1]) if authors else "paper"
    title_words = re.findall(r"[A-Za-z0-9]+", item.get("title") or "")
    keyword = _word_slug(title_words[0]) if title_words else "untitled"
    year = _year(item.get("date") or "") or "nd"
    return f"{family}{year}{keyword}" or f"paper-{item['zotero_key'].lower()}"


def safe_filename(citekey: str) -> str:
    clean = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "-", citekey).strip(" .")
    return clean[:100] or "untitled"


def annotation_hash(annotations: list[dict]) -> str:
    raw = json.dumps(annotations, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:16]


def _frontmatter(item: dict, citekey: str) -> str:
    year = _year(item.get("date") or "")
    data = {
        "type": "literature",
        "citekey": citekey,
        "zotero_key": item["zotero_key"],
        "title": item.get("title") or "Untitled",
        "authors": item.get("authors") or [],
        "year": int(year) if year else None,
        "doi": item.get("doi") or None,
        "url": item.get("url") or None,
        "tags": item.get("tags") or [],
        "paperflow_managed": True,
    }
    yaml_text = yaml.safe_dump(
        data, allow_unicode=True, sort_keys=False, default_flow_style=False
    ).strip()
    return f"---\n{yaml_text}\n---"


def _metadata(item: dict) -> str:
    authors = ", ".join(item.get("authors") or []) or "Unknown"
    year = _year(item.get("date") or "") or "Unknown"
    rows = [f"> **Authors:** {authors}  ", f"> **Year:** {year}  "]
    if item.get("venue"):
        rows.append(f"> **Venue:** {item['venue']}  ")
    if item.get("doi"):
        doi = item["doi"]
        rows.append(f"> **DOI:** [{doi}](https://doi.org/{doi})  ")
    if item.get("url"):
        rows.append(f"> **Source:** [Open link]({item['url']})")
    abstract = (item.get("abstract") or "_No abstract in Zotero._").strip()
    return "\n".join(
        [
            METADATA_BEGIN,
            f"# {item.get('title') or 'Untitled'}",
            "",
            "> [!info]",
            *rows,
            "",
            "## Abstract",
            "",
            abstract,
            METADATA_END,
        ]
    )


def _annotations(item: dict) -> str:
    lines = [ANNOTATIONS_BEGIN, "## Annotations", ""]
    annotations = item.get("annotations") or []
    if not annotations:
        lines.append("_No PDF annotations in Zotero._")
    for annotation in annotations:
        page = annotation.get("page") or "?"
        kind = annotation.get("type") or "annotation"
        lines.append(f"> [!quote] Page {page} · {kind}")
        text = (annotation.get("text") or "").strip()
        comment = (annotation.get("comment") or "").strip()
        if text:
            lines.extend(f"> {line}" for line in text.splitlines())
        if comment:
            lines.append(">")
            lines.extend(f"> **Note:** {line}" for line in comment.splitlines())
        lines.append("")
    lines.append(ANNOTATIONS_END)
    return "\n".join(lines).rstrip()


def render_note(item: dict, citekey: str) -> str:
    return (
        f"{_frontmatter(item, citekey)}\n\n{_metadata(item)}\n\n"
        f"{_annotations(item)}\n\n## My Notes\n\n"
    )


def _replace_block(text: str, begin: str, end: str, replacement: str) -> str:
    pattern = re.compile(re.escape(begin) + r".*?" + re.escape(end), re.DOTALL)
    if not pattern.search(text):
        raise ValueError(f"Missing PaperFlow managed block: {begin}")
    return pattern.sub(lambda _: replacement, text, count=1)


def update_note(path: Path, item: dict, citekey: str) -> None:
    if not path.exists():
        path.write_text(render_note(item, citekey), encoding="utf-8")
        return
    text = path.read_text(encoding="utf-8")
    frontmatter = re.compile(r"\A---\r?\n.*?\r?\n---", re.DOTALL)
    if not frontmatter.search(text):
        raise ValueError(f"Cannot safely update {path.name}: YAML frontmatter is missing")
    text = frontmatter.sub(lambda _: _frontmatter(item, citekey), text, count=1)
    text = _replace_block(text, METADATA_BEGIN, METADATA_END, _metadata(item))
    text = _replace_block(text, ANNOTATIONS_BEGIN, ANNOTATIONS_END, _annotations(item))
    path.write_text(text.rstrip() + "\n", encoding="utf-8")
