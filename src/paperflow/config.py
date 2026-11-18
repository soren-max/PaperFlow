from __future__ import annotations

import json
import os
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote, urlsplit

CONFIG_DIR = ".paperflow"
CONFIG_NAME = "config.toml"
MANIFEST_NAME = "manifest.json"
DEFAULT_LOCAL_API_URL = "http://127.0.0.1:23119"
ZOTERO_BACKENDS = ("auto", "bridge", "local_api")
RESEARCH_MARKERS = (
    "RESEARCH_HOME.md",
    "EIGHT_WEEK_ROADMAP.md",
    "RESEARCH_STATE.md",
    "HYPOTHESIS_REGISTRY.md",
)
_WINDOWS_DRIVE = re.compile(r"^([A-Za-z]):(?:[\\/](.*))?$")
_WSL_UNC = re.compile(r"^\\\\wsl(?:\.localhost|\$)\\[^\\]+(?:\\(.*))?$", re.IGNORECASE)


def normalize_local_path(value: str | Path, *, platform_name: str | None = None) -> Path:
    """Resolve a local, file://, Windows, or WSL UNC path for the active OS."""
    target_os = os.name if platform_name is None else platform_name
    raw = os.path.expandvars(str(value).strip())
    if raw.startswith("file://"):
        parsed = urlsplit(raw)
        raw = unquote(parsed.path)
        if re.fullmatch(r"/[A-Za-z]:/.*", raw):
            raw = raw[1:]
    if target_os != "nt":
        if match := _WINDOWS_DRIVE.match(raw):
            drive = match.group(1).lower()
            rest = (match.group(2) or "").replace("\\", "/").lstrip("/")
            return Path(f"/mnt/{drive}/{rest}" if rest else f"/mnt/{drive}")
        if match := _WSL_UNC.match(raw):
            rest = (match.group(1) or "").replace("\\", "/").lstrip("/")
            return Path(f"/{rest}" if rest else "/")
    return Path(raw).expanduser()


def resolve_vault_relative_path(
    value: str | Path, vault: Path, *, platform_name: str | None = None
) -> Path:
    """Resolve a path relative to the vault unless it is already explicit/cross-OS."""
    raw = str(value).strip()
    if (
        raw.startswith(("file://", "~", "$"))
        or _WINDOWS_DRIVE.match(raw)
        or _WSL_UNC.match(raw)
        or Path(raw).is_absolute()
    ):
        return normalize_local_path(raw, platform_name=platform_name).resolve()
    return (vault / normalize_local_path(raw, platform_name=platform_name)).resolve()


@dataclass(frozen=True)
class Config:
    vault: Path
    literature_dir: str = "01-Literature"
    collection_keys: tuple[str, ...] = ()
    research_dir: str = ""
    experiments_dir: str = ""
    zotero_backend: str = "auto"
    zotero_local_api_url: str = DEFAULT_LOCAL_API_URL

    @property
    def state_dir(self) -> Path:
        return self.vault / CONFIG_DIR

    @property
    def manifest_path(self) -> Path:
        return self.state_dir / MANIFEST_NAME

    @property
    def literature_path(self) -> Path:
        return self.vault / self.literature_dir

    @property
    def research_path(self) -> Path | None:
        if self.research_dir:
            return resolve_vault_relative_path(self.research_dir, self.vault)
        candidate = self.vault / "research"
        if candidate.is_dir() and any((candidate / marker).is_file() for marker in RESEARCH_MARKERS):
            return candidate
        return None

    @property
    def experiments_path(self) -> Path | None:
        if self.experiments_dir:
            return resolve_vault_relative_path(self.experiments_dir, self.vault)
        candidate = self.vault / "experiments"
        if candidate.is_dir():
            return candidate
        return None


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
    lines = [
        f"vault = {vault_json}",
        f"literature_dir = {literature_json}",
        f"collection_keys = {collection_keys}",
    ]
    if config.research_dir:
        lines.append(f"research_dir = {json.dumps(config.research_dir, ensure_ascii=False)}")
    if config.experiments_dir:
        lines.append(f"experiments_dir = {json.dumps(config.experiments_dir, ensure_ascii=False)}")
    if config.zotero_backend != "auto":
        lines.append(f"zotero_backend = {json.dumps(config.zotero_backend, ensure_ascii=False)}")
    if config.zotero_local_api_url != DEFAULT_LOCAL_API_URL:
        lines.append(
            f"zotero_local_api_url = {json.dumps(config.zotero_local_api_url, ensure_ascii=False)}"
        )
    config_path(config.vault).write_text("\n".join(lines) + "\n", encoding="utf-8")
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
        candidate = config_path(
            normalize_local_path(pointer.read_text(encoding="utf-8").strip())
        )
        if candidate.exists():
            return candidate
    return None


def load_config(explicit: Path | None = None) -> Config:
    path = find_config(explicit)
    if path is None:
        raise FileNotFoundError("PaperFlow is not initialized. Run: paperflow init")
    with path.open("rb") as handle:
        data = tomllib.load(handle)
    vault = normalize_local_path(data["vault"])
    research_table = data.get("research") if isinstance(data.get("research"), dict) else {}
    zotero_table = data.get("zotero") if isinstance(data.get("zotero"), dict) else {}
    zotero_backend = str(
        data.get("zotero_backend", zotero_table.get("backend", "auto"))
    ).strip()
    if zotero_backend not in ZOTERO_BACKENDS:
        raise ValueError(f"Invalid zotero_backend: {zotero_backend}")
    return Config(
        vault=vault,
        literature_dir=data.get("literature_dir", "01-Literature"),
        collection_keys=tuple(data.get("collection_keys", ())),
        research_dir=str(data.get("research_dir", research_table.get("research_dir", ""))),
        experiments_dir=str(
            data.get("experiments_dir", research_table.get("experiments_dir", ""))
        ),
        zotero_backend=zotero_backend,
        zotero_local_api_url=str(
            data.get(
                "zotero_local_api_url",
                zotero_table.get("local_api_url", DEFAULT_LOCAL_API_URL),
            )
        ).rstrip("/"),
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
