from __future__ import annotations

import json
import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

CONFIG_DIR = ".paperflow"
CONFIG_NAME = "config.toml"
MANIFEST_NAME = "manifest.json"


@dataclass(frozen=True)
class Config:
    vault: Path
    literature_dir: str = "01-Literature"
    collection_keys: tuple[str, ...] = ()

    @property
    def state_dir(self) -> Path:
        return self.vault / CONFIG_DIR

    @property
    def manifest_path(self) -> Path:
        return self.state_dir / MANIFEST_NAME

    @property
    def literature_path(self) -> Path:
        return self.vault / self.literature_dir


def user_state_dir() -> Path:
    base = os.environ.get("APPDATA")
    return Path(base) / "PaperFlow" if base else Path.home() / ".config" / "paperflow"


def active_vault_path() -> Path:
    return user_state_dir() / "active-vault"


def config_path(vault: Path) -> Path:
    return vault / CONFIG_DIR / CONFIG_NAME


def write_config(config: Config) -> None:
    config.state_dir.mkdir(parents=True, exist_ok=True)
    vault_json = json.dumps(str(config.vault.resolve()), ensure_ascii=False)
    literature_json = json.dumps(config.literature_dir, ensure_ascii=False)
    collection_keys = json.dumps(list(config.collection_keys), ensure_ascii=False)
    config_path(config.vault).write_text(
        f"vault = {vault_json}\n"
        f"literature_dir = {literature_json}\n"
        f"collection_keys = {collection_keys}\n",
        encoding="utf-8",
    )
    pointer = active_vault_path()
    pointer.parent.mkdir(parents=True, exist_ok=True)
    pointer.write_text(str(config.vault.resolve()), encoding="utf-8")


def find_config(explicit: Path | None = None) -> Path | None:
    if explicit:
        candidate = explicit / CONFIG_DIR / CONFIG_NAME if explicit.is_dir() else explicit
        return candidate if candidate.exists() else None
    for parent in (Path.cwd(), *Path.cwd().parents):
        candidate = config_path(parent)
        if candidate.exists():
            return candidate
    pointer = active_vault_path()
    if pointer.exists():
        candidate = config_path(Path(pointer.read_text(encoding="utf-8").strip()))
        if candidate.exists():
            return candidate
    return None


def load_config(explicit: Path | None = None) -> Config:
    path = find_config(explicit)
    if path is None:
        raise FileNotFoundError("PaperFlow is not initialized. Run: paperflow init")
    with path.open("rb") as handle:
        data = tomllib.load(handle)
    vault = Path(data["vault"]).expanduser()
    return Config(
        vault=vault,
        literature_dir=data.get("literature_dir", "01-Literature"),
        collection_keys=tuple(data.get("collection_keys", ())),
    )


def load_manifest(config: Config) -> dict:
    if not config.manifest_path.exists():
        return {"version": 1, "last_sync_at": None, "items": {}}
    return json.loads(config.manifest_path.read_text(encoding="utf-8"))


def save_manifest(config: Config, manifest: dict) -> None:
    config.state_dir.mkdir(parents=True, exist_ok=True)
    temporary = config.manifest_path.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    temporary.replace(config.manifest_path)
