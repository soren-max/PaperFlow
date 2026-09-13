from __future__ import annotations

import json
import subprocess

from paperflow.cli import _ordered_collections, _scope_text
from paperflow.config import Config, load_config, write_config
from paperflow.zotero import Collection, fetch_library, list_collections


def test_multiple_collection_keys_round_trip(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    config = Config(tmp_path / "Vault", collection_keys=("PARENT1", "OTHER22"))
    write_config(config)

    loaded = load_config(config.vault)

    assert loaded.collection_keys == ("PARENT1", "OTHER22")


def test_existing_v1_config_upgrades_to_entire_library(tmp_path):
    state = tmp_path / ".paperflow"
    state.mkdir()
    (state / "config.toml").write_text(
        f'vault = {json.dumps(str(tmp_path))}\nliterature_dir = "01-Literature"\n',
        encoding="utf-8",
    )

    loaded = load_config(tmp_path)

    assert loaded.collection_keys == ()


def test_collection_tree_is_nested_and_sorted():
    collections = [
        Collection("CHILD", "RAG", "PARENT"),
        Collection("OTHER", "Archive"),
        Collection("PARENT", "AI Agents"),
    ]

    assert [(item.name, depth) for item, depth in _ordered_collections(collections)] == [
        ("AI Agents", 0),
        ("RAG", 1),
        ("Archive", 0),
    ]


def test_collection_rename_uses_key_and_displays_current_name():
    keys = ("STABLE01",)

    assert _scope_text(keys, [Collection("STABLE01", "New Name")]) == "New Name"
    assert keys == ("STABLE01",)


def test_zotero_collection_listing_uses_cli_json(monkeypatch):
    payload = [
        {"key": "PARENT", "name": "AI Agents", "parent_key": None, "item_count": 2},
        {"key": "CHILD", "name": "RAG", "parent_key": "PARENT", "item_count": 1},
    ]
    monkeypatch.setattr("paperflow.zotero._run_zot", lambda *args, **kwargs: json.dumps(payload))

    collections = list_collections()

    assert collections == [
        Collection("PARENT", "AI Agents", None, 2),
        Collection("CHILD", "RAG", "PARENT", 1),
    ]


def test_zotero_subprocess_is_forced_to_utf8(monkeypatch):
    def fake_run(*args, **kwargs):
        assert kwargs["env"]["PYTHONUTF8"] == "1"
        assert kwargs["env"]["PYTHONIOENCODING"] == "utf-8"
        return subprocess.CompletedProcess(args[0], 0, stdout="[]", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    assert list_collections() == []


def test_selected_keys_are_passed_to_recursive_deduplicating_script(monkeypatch):
    captured = {}

    def fake_run(arguments, *, input_text=None, timeout=30):
        captured["script"] = input_text
        return '{"items": [], "selected_collections": []}'

    monkeypatch.setattr("paperflow.zotero._run_zot", fake_run)

    assert fetch_library(("PARENT", "CHILD")) == []
    assert '["PARENT", "CHILD"]' in captured["script"]
    assert "getDescendents(false, 'collection')" in captured["script"]
    assert "seenItems[scopedItem.id]" in captured["script"]
