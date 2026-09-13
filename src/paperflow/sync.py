from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from .config import Config, load_manifest, save_manifest
from .markdown import annotation_hash, choose_citekey, safe_filename, update_note


@dataclass
class SyncResult:
    total: int = 0
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    failed: int = 0
    errors: list[str] = field(default_factory=list)


def changes(items: list[dict], manifest: dict, config: Config) -> tuple[int, int, int]:
    changed = 0
    new_annotations = 0
    known = manifest.get("items", {})
    for item in items:
        old = known.get(item["zotero_key"])
        note_missing = bool(old) and not (config.vault / old.get("note_path", "")).exists()
        current_hash = annotation_hash(item.get("annotations") or [])
        annotations_changed = old and old.get("annotations_hash") != current_hash
        if (
            not old
            or old.get("source_modified_at") != item.get("source_modified_at")
            or annotations_changed
            or note_missing
        ):
            changed += 1
        old_count = old.get("annotation_count", 0) if old else 0
        if not old or old.get("annotations_hash") != current_hash:
            new_annotations += max(len(item.get("annotations") or []) - old_count, 0)
    scope_keys = {item["zotero_key"] for item in items}
    missing_notes = sum(
        1
        for key, entry in known.items()
        if key in scope_keys and not (config.vault / entry.get("note_path", "")).exists()
    )
    return changed, new_annotations, missing_notes


def synchronize(config: Config, items: list[dict]) -> SyncResult:
    manifest = load_manifest(config)
    records = manifest.setdefault("items", {})
    config.literature_path.mkdir(parents=True, exist_ok=True)
    result = SyncResult(total=len(items))
    used = {entry.get("citekey") for entry in records.values()}
    now = datetime.now(UTC).isoformat()

    for item in sorted(items, key=lambda value: (value.get("title") or "").casefold()):
        key = item["zotero_key"]
        previous = records.get(key, {})
        citekey = choose_citekey(item, previous.get("citekey"))
        if not previous and citekey in used:
            citekey = f"{citekey}-{key.lower()}"
        used.add(citekey)
        relative = (
            previous.get("note_path") or f"{config.literature_dir}/{safe_filename(citekey)}.md"
        )
        path = config.vault / relative
        ann_hash = annotation_hash(item.get("annotations") or [])
        source_changed = previous.get("source_modified_at") != item.get("source_modified_at")
        annotations_changed = previous.get("annotations_hash") != ann_hash
        should_write = not path.exists() or source_changed or annotations_changed
        try:
            if should_write:
                existed = path.exists()
                path.parent.mkdir(parents=True, exist_ok=True)
                update_note(path, item, citekey)
                result.updated += int(existed)
                result.created += int(not existed)
            else:
                result.unchanged += 1
            records[key] = {
                "citekey": citekey,
                "note_path": relative.replace("\\", "/"),
                "source_modified_at": item.get("source_modified_at") or "",
                "annotations_hash": ann_hash,
                "annotation_count": len(item.get("annotations") or []),
                "last_synced_at": now,
            }
        except (OSError, ValueError) as error:
            result.failed += 1
            result.errors.append(f"{citekey}: {error}")

    manifest["version"] = 1
    manifest["last_sync_at"] = now
    save_manifest(config, manifest)
    return result
