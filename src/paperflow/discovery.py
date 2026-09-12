from __future__ import annotations

import json
import os
import shutil
from pathlib import Path


def discover_vaults() -> list[Path]:
    candidates: list[Path] = []
    obsidian_config = Path(os.environ.get("APPDATA", "")) / "obsidian" / "obsidian.json"
    if obsidian_config.exists():
        try:
            vaults = json.loads(obsidian_config.read_text(encoding="utf-8")).get("vaults", {})
            candidates.extend(Path(entry["path"]) for entry in vaults.values() if entry.get("path"))
        except (OSError, ValueError, TypeError):
            pass
    current = Path.cwd()
    candidates.extend(
        parent for parent in (current, *current.parents) if (parent / ".obsidian").is_dir()
    )
    unique: list[Path] = []
    for path in candidates:
        resolved = path.expanduser().resolve()
        if resolved.is_dir() and resolved not in unique:
            unique.append(resolved)
    return unique


def command_available(name: str) -> bool:
    return shutil.which(name) is not None


def zotero_profile_found() -> bool:
    roaming = Path(os.environ.get("APPDATA", ""))
    return any((roaming / "Zotero" / "Zotero" / "Profiles").glob("*.default*"))
