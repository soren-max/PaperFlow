from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

from .config import normalize_local_path


def _roaming_appdata_dirs() -> list[Path]:
    dirs: list[Path] = []
    appdata = os.environ.get("APPDATA")
    if appdata:
        dirs.append(Path(appdata))
    if os.name != "nt":
        for mount in sorted(Path("/mnt").glob("*/Users/*/AppData/Roaming")):
            if mount.is_dir():
                dirs.append(mount)
    return dirs


def discover_vaults() -> list[Path]:
    candidates: list[Path] = []
    for roaming in _roaming_appdata_dirs():
        obsidian_config = roaming / "obsidian" / "obsidian.json"
        if not obsidian_config.exists():
            continue
        try:
            vaults = json.loads(obsidian_config.read_text(encoding="utf-8")).get("vaults", {})
            candidates.extend(
                normalize_local_path(entry["path"])
                for entry in vaults.values()
                if entry.get("path")
            )
        except (OSError, ValueError, TypeError):
            pass
    current = Path.cwd()
    candidates.extend(
        parent
        for parent in (current, *current.parents)
        if (parent / ".obsidian").is_dir() or (parent / ".paperflow" / "config.toml").is_file()
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
    return any(
        any((roaming / "Zotero" / "Zotero" / "Profiles").glob("*.default*"))
        for roaming in _roaming_appdata_dirs()
    )
