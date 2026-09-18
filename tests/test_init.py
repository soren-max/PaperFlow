from pathlib import Path

import pytest
from typer.testing import CliRunner

from paperflow.cli import LEGACY_VAULT_AGENTS, PRE_TRIAGE_VAULT_AGENTS, app


def test_init_installs_codex_skill_agents_and_readable_templates(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    monkeypatch.setattr("paperflow.cli.ping", lambda timeout=5: (False, "offline"))
    monkeypatch.setattr("paperflow.cli.zotero_profile_found", lambda: False)
    vault = tmp_path / "Research Vault"

    result = CliRunner().invoke(app, ["init", str(vault)])

    assert result.exit_code == 0, result.output
    agents = (vault / "AGENTS.md").read_text(encoding="utf-8")
    skill = (vault / ".agents/skills/paperflow/SKILL.md").read_text(encoding="utf-8")
    concept = (vault / "90-Templates/Concept.md").read_text(encoding="utf-8")
    synthesis = (vault / "90-Templates/Synthesis.md").read_text(encoding="utf-8")
    question = (vault / "90-Templates/Question.md").read_text(encoding="utf-8")
    assert (vault / "00-Research-Areas").is_dir()
    assert "Zotero is the bibliographic source of truth" in agents
    assert "00-Research-Areas/" in agents
    assert "00-Research-Areas/" in skill
    assert "01-Literature/" in skill
    assert "02-Concepts/" in skill
    assert "03-Synthesis/" in skill
    assert "04-Questions/" in skill
    assert "## Triage a paper (V3)" in skill
    assert "to triage synced Zotero papers" in skill
    assert "## Process a completed paper (V2)" in skill
    assert (vault / ".agents/skills/paperflow/prompts/triage.md").is_file()
    assert "processing_level: deep" in (
        vault / ".agents/skills/paperflow/prompts/triage.md"
    ).read_text(encoding="utf-8")
    assert (vault / ".agents/skills/paperflow/prompts/paper-map.md").is_file()
    assert (vault / ".agents/skills/paperflow/prompts/section-evidence.md").is_file()
    assert (vault / ".agents/skills/paperflow/prompts/legacy-migration.md").is_file()
    assert (vault / "90-Templates/ResearchArea.md").is_file()
    assert "## Evidence" in concept
    assert "## Sources" in synthesis
    assert "## Working Hypotheses" in question


def test_init_does_not_overwrite_customized_codex_files(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    monkeypatch.setattr("paperflow.cli.ping", lambda timeout=5: (False, "offline"))
    monkeypatch.setattr("paperflow.cli.zotero_profile_found", lambda: False)
    vault = tmp_path / "Vault"
    (vault / "90-Templates").mkdir(parents=True)
    (vault / "AGENTS.md").write_text("custom agents\n", encoding="utf-8")
    (vault / "90-Templates/Concept.md").write_text("custom concept\n", encoding="utf-8")

    result = CliRunner().invoke(app, ["init", str(vault)])

    assert result.exit_code == 0, result.output
    assert (vault / "AGENTS.md").read_text(encoding="utf-8") == "custom agents\n"
    assert (vault / "90-Templates/Concept.md").read_text(encoding="utf-8") == "custom concept\n"
    assert (vault / ".agents/skills/paperflow/SKILL.md").is_file()


def test_init_upgrades_original_legacy_agents(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    monkeypatch.setattr("paperflow.cli.ping", lambda timeout=5: (False, "offline"))
    monkeypatch.setattr("paperflow.cli.zotero_profile_found", lambda: False)
    vault = tmp_path / "Legacy Vault"
    vault.mkdir()
    (vault / "AGENTS.md").write_text(LEGACY_VAULT_AGENTS, encoding="utf-8")

    result = CliRunner().invoke(app, ["init", str(vault)])

    assert result.exit_code == 0, result.output
    upgraded = (vault / "AGENTS.md").read_text(encoding="utf-8")
    assert upgraded != LEGACY_VAULT_AGENTS
    assert "Never invent metadata, quotes, findings, or citations" in upgraded
    assert "00-Research-Areas/" in upgraded


def test_init_upgrades_a_pre_triage_agents_file(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    monkeypatch.setattr("paperflow.cli.ping", lambda timeout=5: (False, "offline"))
    monkeypatch.setattr("paperflow.cli.zotero_profile_found", lambda: False)
    vault = tmp_path / "Pre Triage Vault"
    vault.mkdir()
    (vault / "AGENTS.md").write_text(PRE_TRIAGE_VAULT_AGENTS, encoding="utf-8")

    result = CliRunner().invoke(app, ["init", str(vault)])

    assert result.exit_code == 0, result.output
    upgraded = (vault / "AGENTS.md").read_text(encoding="utf-8")
    assert upgraded != PRE_TRIAGE_VAULT_AGENTS
    assert "00-Research-Areas/" in upgraded


@pytest.mark.parametrize("fixture", ["pre_triage_skill.md", "pre_triage_migration_skill.md"])
def test_init_upgrades_only_the_original_pre_triage_skill(tmp_path, monkeypatch, fixture):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    monkeypatch.setattr("paperflow.cli.ping", lambda timeout=5: (False, "offline"))
    monkeypatch.setattr("paperflow.cli.zotero_profile_found", lambda: False)
    original = (Path(__file__).parent / "fixtures" / fixture).read_text(encoding="utf-8")
    vault = tmp_path / "Old Vault"
    skill = vault / ".agents/skills/paperflow/SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text(original, encoding="utf-8")

    result = CliRunner().invoke(app, ["init", str(vault)])
    assert result.exit_code == 0, result.output
    upgraded = skill.read_text(encoding="utf-8")
    assert "## Triage a paper (V3)" in upgraded
    assert "prompts/triage.md" in upgraded
    assert "Run `paperflow triage <citekey>` again" in upgraded

    skill.write_text(original + "\nMy customization.\n", encoding="utf-8")
    result = CliRunner().invoke(app, ["init", str(vault)])
    assert result.exit_code == 0, result.output
    assert skill.read_text(encoding="utf-8").endswith("My customization.\n")
