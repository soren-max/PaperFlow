"""Native CLI smoke test for the existing Windows command sequence."""

from typer.testing import CliRunner

from paperflow.cli import app
from paperflow.config import Config, write_config


def test_sync_ingest_process_doctor_via_native_cli(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    vault = tmp_path / "Research Vault"
    config = Config(vault)
    write_config(config)
    paper = {
        "zotero_key": "ABCD1234",
        "citekey": "example2026",
        "title": "Example Paper",
        "authors": ["A Researcher"],
        "date": "2026",
        "abstract": "An example.",
        "source_modified_at": "2026-01-01",
        "annotations": [],
    }
    pdf = tmp_path / "paper.pdf"
    pdf.write_bytes(b"fake PDF bytes")
    monkeypatch.setattr("paperflow.cli.fetch_library", lambda keys: [paper])
    monkeypatch.setattr(
        "paperflow.ingest.fetch_paper_pdf",
        lambda key: {
            "zotero_key": key,
            "title": paper["title"],
            "abstract": paper["abstract"],
            "pdfs": [{"key": "PDF12345", "path": str(pdf)}],
        },
    )
    monkeypatch.setattr(
        "paperflow.ingest._pymupdf_pages",
        lambda path: ["# Example Paper\n\n## Results\n\nA measured result."],
    )
    monkeypatch.setattr("paperflow.cli.ping", lambda: (True, "ready"))
    monkeypatch.setattr("paperflow.cli.command_available", lambda command: True)

    runner = CliRunner()
    for command in (
        ["sync"],
        ["ingest", "example2026"],
        ["process", "example2026"],
        ["doctor"],
    ):
        result = runner.invoke(app, [*command, "--vault", str(vault)])
        assert result.exit_code == 0, (command, result.output)

    assert (vault / "01-Literature" / "example2026.md").is_file()
    assert (vault / ".paperflow" / "papers" / "ABCD1234" / "source.md").is_file()
