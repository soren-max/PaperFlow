from typer.testing import CliRunner

from paperflow.cli import LEGACY_VAULT_AGENTS, app


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
    assert "Zotero is the bibliographic source of truth" in agents
    assert "01-Literature/" in skill
    assert "02-Concepts/" in skill
    assert "03-Synthesis/" in skill
    assert "04-Questions/" in skill
    assert "## Process a completed paper (V2)" in skill
    assert (vault / ".agents/skills/paperflow/prompts/paper-map.md").is_file()
    assert (vault / ".agents/skills/paperflow/prompts/section-evidence.md").is_file()
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
