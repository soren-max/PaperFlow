from __future__ import annotations

import json
import os
import sys
from datetime import UTC, datetime
from importlib.resources import files
from pathlib import Path
from typing import Annotated

import questionary
import typer
from questionary import Choice
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .config import Config, config_path, load_config, load_manifest, save_manifest, write_config
from .discovery import command_available, discover_vaults, zotero_profile_found
from .ingest import ingest as ingest_paper
from .migration import reconcile as reconcile_legacy
from .process import inspect as inspect_paper
from .process import publish_note as publish_paper_note
from .sync import changes, synchronize
from .triage import summary as triage_summary
from .triage import triage as triage_papers
from .zotero import (
    Collection,
    ZoteroUnavailable,
    fetch_library,
    fetch_snapshot,
    list_collections,
    ping,
)

if os.name == "nt":
    # Windows redirection can inherit a legacy code page even though the console supports UTF-8.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


app = typer.Typer(
    name="paperflow",
    help="Zotero facts → clean Markdown → Codex knowledge",
    no_args_is_help=False,
    invoke_without_command=True,
)
console = Console()

VAULT_RESOURCES = {
    "AGENTS.md": "AGENTS.md",
    ".agents/skills/paperflow/SKILL.md": "skills/paperflow/SKILL.md",
    ".agents/skills/paperflow/prompts/triage.md": "skills/paperflow/prompts/triage.md",
    ".agents/skills/paperflow/prompts/paper-map.md": "skills/paperflow/prompts/paper-map.md",
    ".agents/skills/paperflow/prompts/section-evidence.md": "skills/paperflow/prompts/section-evidence.md",
    ".agents/skills/paperflow/prompts/cards.md": "skills/paperflow/prompts/cards.md",
    ".agents/skills/paperflow/prompts/paper-synthesis.md": "skills/paperflow/prompts/paper-synthesis.md",
    ".agents/skills/paperflow/prompts/knowledge-integration.md": "skills/paperflow/prompts/knowledge-integration.md",
    ".agents/skills/paperflow/prompts/legacy-migration.md": "skills/paperflow/prompts/legacy-migration.md",
    "90-Templates/ResearchArea.md": "templates/ResearchArea.md",
    "90-Templates/Concept.md": "templates/Concept.md",
    "90-Templates/Synthesis.md": "templates/Synthesis.md",
    "90-Templates/Question.md": "templates/Question.md",
}
VAULT_FOLDERS = (
    "00-Research-Areas",
    "01-Literature",
    "02-Concepts",
    "03-Synthesis",
    "04-Questions",
)
TRIAGE_LABELS = {
    "ready": "packet ready",
    "card": "card valid",
    "invalid": "invalid",
    "stale": "note changed",
    "missing-note": "note missing",
}
TRIAGE_TABLE_LIMIT = 25
LEGACY_VAULT_AGENTS = """# PaperFlow Vault

This is a personal research knowledge base.

- `01-Literature/` contains source-grounded Zotero literature notes. Preserve PaperFlow managed blocks and `My Notes`.
- `02-Concepts/` contains durable ideas connected across papers.
- `03-Synthesis/` contains cross-paper comparisons, arguments, and writing material.
- `04-Questions/` contains open research questions and resolved answers worth keeping.

Treat Literature as evidence. Use Codex to turn that evidence into Concepts and Synthesis. Mark uncertainty explicitly and prefer Obsidian links between durable notes.
"""
PRE_TRIAGE_VAULT_AGENTS = """# PaperFlow research rules

- Zotero is the bibliographic source of truth.
- `01-Literature/` is source-grounded. Never invent metadata, quotes, findings, or citations, and never silently turn an inference into a paper's claim.
- Put cross-paper reasoning in `02-Concepts/` or `03-Synthesis/`, retaining the source literature citekeys.
- Prefer updating an existing Concept or Synthesis over creating a duplicate.
- Do not modify PaperFlow-managed blocks or `## My Notes` unless explicitly requested.
- Keep Markdown human-readable and mark inference, uncertainty, and missing evidence clearly.
"""
REPLACEABLE_VAULT_AGENTS = (LEGACY_VAULT_AGENTS, PRE_TRIAGE_VAULT_AGENTS)


def _install_vault_resources(vault: Path) -> None:
    resources = files("paperflow").joinpath("resources")
    for destination, source in VAULT_RESOURCES.items():
        path = vault / destination
        if path.exists():
            is_legacy_agents = (
                destination == "AGENTS.md"
                and path.read_text(encoding="utf-8") in REPLACEABLE_VAULT_AGENTS
            )
            if not is_legacy_agents:
                continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(resources.joinpath(source).read_text(encoding="utf-8"), encoding="utf-8")


def _get_config(path: Path | None = None) -> Config:
    try:
        return load_config(path)
    except (FileNotFoundError, KeyError, OSError, ValueError) as error:
        console.print(f"[red]✗[/red] {error}")
        raise typer.Exit(1) from error


def _relative_time(value: str | None) -> str:
    if not value:
        return "Never"
    try:
        moment = datetime.fromisoformat(value)
        seconds = max(0, int((datetime.now(UTC) - moment).total_seconds()))
    except ValueError:
        return value
    if seconds < 60:
        return "Just now"
    if seconds < 3600:
        return f"{seconds // 60} minutes ago"
    if seconds < 86400:
        return f"{seconds // 3600} hours ago"
    return f"{seconds // 86400} days ago"


def _ordered_collections(collections: list[Collection]) -> list[tuple[Collection, int]]:
    children: dict[str | None, list[Collection]] = {}
    keys = {collection.key for collection in collections}
    for collection in collections:
        parent = collection.parent_key if collection.parent_key in keys else None
        children.setdefault(parent, []).append(collection)
    ordered: list[tuple[Collection, int]] = []

    def visit(parent: str | None, depth: int) -> None:
        for collection in sorted(children.get(parent, []), key=lambda item: item.name.casefold()):
            ordered.append((collection, depth))
            visit(collection.key, depth + 1)

    visit(None, 0)
    return ordered


def _choose_scope(collections: list[Collection], current_keys: tuple[str, ...]) -> tuple[str, ...]:
    if not collections:
        return ()
    mode = questionary.select(
        "Zotero scope",
        choices=["Entire Library", "Selected collections"],
        default="Selected collections" if current_keys else "Entire Library",
        instruction="(↑/↓ move, Enter select)",
    ).ask()
    if mode is None:
        raise typer.Abort()
    if mode == "Entire Library":
        return ()
    available = {collection.key for collection in collections}
    choices = [
        Choice(
            title=f"{'  ' * depth}{collection.name}",
            value=collection.key,
            checked=collection.key in current_keys,
        )
        for collection, depth in _ordered_collections(collections)
    ]
    selected = questionary.checkbox(
        "Select collections (nested collections are included)",
        choices=choices,
        instruction="(Space toggle, Enter finish)",
    ).ask()
    if selected is None:
        raise typer.Abort()
    return tuple(key for key in selected if key in available)


def _scope_text(keys: tuple[str, ...], collections: list[Collection] | None = None) -> str:
    if not keys:
        return "Entire Library"
    names = {collection.key: collection.name for collection in collections or []}
    return ", ".join(names.get(key, key) for key in keys)


def _paper_count(count: int) -> str:
    return f"{count:,} {'paper' if count == 1 else 'papers'}"


@app.callback()
def main(ctx: typer.Context) -> None:
    """Show status when invoked without a command."""
    if ctx.invoked_subcommand is None:
        status()


@app.command("init")
def initialize(
    vault: Annotated[Path | None, typer.Argument(help="Existing or new Obsidian vault")] = None,
) -> None:
    """Discover your Obsidian vault and prepare it for PaperFlow."""
    if vault is None:
        candidates = discover_vaults()
        if len(candidates) == 1:
            vault = candidates[0]
        elif len(candidates) > 1:
            console.print("\n[bold]Obsidian vaults[/bold]")
            for index, candidate in enumerate(candidates, 1):
                console.print(f"  {index}. {candidate}")
            selected = typer.prompt("Choose a vault", type=int, default=1)
            if not 1 <= selected <= len(candidates):
                raise typer.BadParameter("Choose one of the listed vault numbers")
            vault = candidates[selected - 1]
        else:
            vault = Path(typer.prompt("Obsidian vault path"))
    vault = vault.expanduser().resolve()
    vault.mkdir(parents=True, exist_ok=True)
    existing = load_config(vault) if config_path(vault).exists() else Config(vault=vault)
    config = Config(
        vault=vault,
        literature_dir=existing.literature_dir,
        collection_keys=existing.collection_keys,
    )
    for folder in VAULT_FOLDERS:
        (vault / folder).mkdir(exist_ok=True)
    _install_vault_resources(vault)
    ok, _ = ping(timeout=5)
    if ok:
        try:
            collections = list_collections()
            config = Config(
                vault=vault,
                literature_dir=config.literature_dir,
                collection_keys=_choose_scope(collections, config.collection_keys),
            )
            with console.status("Counting selected papers…"):
                selected_count = len(fetch_library(config.collection_keys))
        except ZoteroUnavailable as error:
            collections = []
            selected_count = None
            console.print(f"[yellow]![/yellow] Could not read Zotero collections: {error}")
    else:
        collections = []
        selected_count = None

    write_config(config)
    if not config.manifest_path.exists():
        save_manifest(config, {"version": 1, "last_sync_at": None, "items": {}})

    console.print(Panel.fit(f"[bold green]PaperFlow is ready[/bold green]\n{vault}"))
    console.print(
        "\nPrepared Research Areas, Literature, Concepts, Synthesis, Questions, templates, "
        "and the Codex skill."
    )
    if ok:
        console.print(
            f"[green]✓[/green] Zotero scope — {_scope_text(config.collection_keys, collections)}"
        )
        if selected_count is not None:
            console.print(f"  {_paper_count(selected_count)} selected.")
    elif zotero_profile_found():
        console.print("[yellow]![/yellow] Zotero is installed but not connected.")
        console.print("  Open Zotero, then run [bold]zot init[/bold] once.")
    else:
        console.print("[yellow]![/yellow] Zotero was not found. Install Zotero before syncing.")
    console.print("\nNext: [bold]paperflow sync[/bold]")


@app.command()
def sync(
    vault: Annotated[Path | None, typer.Option("--vault", help="Vault or config path")] = None,
) -> None:
    """Sync Zotero metadata and annotations into Literature notes."""
    config = _get_config(vault)
    console.print("[bold]Reading Zotero…[/bold]")
    try:
        items = fetch_library(config.collection_keys)
    except ZoteroUnavailable as error:
        console.print("\n[red]✗ Cannot reach Zotero.[/red]")
        console.print(str(error))
        console.print("\nOpen Zotero and run:\n\n    [bold]paperflow doctor[/bold]")
        raise typer.Exit(2) from error
    result = synchronize(config, items)
    color = "green" if not result.failed else "yellow"
    console.print(
        Panel.fit(
            f"[{color}][bold]Sync complete[/bold][/{color}]\n"
            f"{result.created} created · {result.updated} updated · {result.unchanged} unchanged"
            + (f" · {result.failed} failed" if result.failed else "")
        )
    )
    for error in result.errors:
        console.print(f"[yellow]![/yellow] {error}")


@app.command()
def ingest(
    paper: Annotated[str, typer.Argument(help="Synced Zotero key or citekey")],
    vault: Annotated[Path | None, typer.Option("--vault", help="Vault or config path")] = None,
    converter: Annotated[
        str, typer.Option("--converter", help="pymupdf4llm or docling")
    ] = "pymupdf4llm",
) -> None:
    """Convert a Zotero PDF into page-located Markdown and reading chunks."""
    config = _get_config(vault)
    try:
        directory, created = ingest_paper(config, paper, converter)
    except (OSError, ValueError, RuntimeError, ZoteroUnavailable) as error:
        console.print(f"[red]✗[/red] {error}")
        raise typer.Exit(1) from error
    word = "Ingested" if created else "Already ingested"
    console.print(f"[green]✓[/green] {word}: {directory}")


@app.command()
def triage(
    paper: Annotated[str | None, typer.Argument(help="One synced Zotero key or citekey")] = None,
    vault: Annotated[Path | None, typer.Option("--vault", help="Vault or config path")] = None,
    limit: Annotated[int, typer.Option("--limit", help="Most papers to triage in one run")] = 25,
    refresh: Annotated[
        bool, typer.Option("--refresh", help="Rebuild packets even when they already exist")
    ] = False,
) -> None:
    """Decide which synced papers deserve deep processing."""
    config = _get_config(vault)
    try:
        result = triage_papers(config, paper, limit, refresh)
    except (OSError, ValueError, KeyError) as error:
        console.print(f"[red]✗[/red] {error}")
        raise typer.Exit(1) from error
    if not result.rows:
        console.print("Nothing to triage. Run [bold]paperflow sync[/bold] first.")
        return
    rows = result.rows
    if len(rows) > TRIAGE_TABLE_LIMIT:
        rows = [row for row in rows if row.status != "card" or row.deep_processing == "yes"]
        if hidden := len(result.rows) - len(rows):
            console.print(f"[dim]… {hidden} validated cards hidden. Narrow with --limit.[/dim]")
    table = Table(show_header=True, header_style="bold")
    for column in ("Paper", "Research area", "Priority", "Deep", "Status"):
        table.add_column(column)
    for row in rows:
        table.add_row(
            row.citekey,
            row.research_area or "—",
            row.priority or "—",
            row.deep_processing or "—",
            TRIAGE_LABELS.get(row.status, row.status),
        )
    console.print(table)
    for row in result.rows:
        for issue in row.issues:
            console.print(f"[yellow]![/yellow] {issue}")
    for missing in result.missing_notes:
        console.print(f"[yellow]![/yellow] Literature note is missing: {missing}")
    console.print(
        f"\n{result.ready} packets prepared · {result.valid} cards valid · "
        f"{result.high} high priority · {result.recommended} recommend deep processing"
    )
    invalid = any(row.issues for row in result.rows)
    pending = any(row.status in ("ready", "stale") for row in result.rows)
    if invalid:
        console.print("Next: correct the issues above and rerun paperflow triage.")
    elif pending:
        console.print("Next: in Codex, triage the prepared packets with prompts/triage.md.")
    if result.remaining:
        console.print(f"{result.remaining} more papers are queued; rerun to continue.")
    if invalid:
        raise typer.Exit(1)


@app.command()
def process(
    paper: Annotated[str, typer.Argument(help="Synced Zotero key or citekey")],
    vault: Annotated[Path | None, typer.Option("--vault", help="Vault or config path")] = None,
    section: Annotated[
        str | None, typer.Option("--section", help="Show bounded section inputs")
    ] = None,
    publish_note: Annotated[
        bool, typer.Option("--publish-note", help="Insert validated note before My Notes")
    ] = False,
) -> None:
    """Reconcile staged artifacts and show the next paper-reading step."""
    config = _get_config(vault)
    try:
        if publish_note:
            note = publish_paper_note(config, paper)
            console.print(f"[green]✓[/green] Literature note: {note}")
        directory, state, issues = inspect_paper(config, paper)
        if section:
            structure = json.loads((directory / "structure.json").read_text(encoding="utf-8"))
            match = next((entry for entry in structure["sections"] if entry["id"] == section), None)
            if match is None:
                raise ValueError(f"Unknown section {section}")
            console.print(
                f"[bold]{match['title']}[/bold], pages {match['page_start']}–{match['page_end']}"
            )
            for chunk in match["chunks"]:
                console.print(f"  {directory / chunk['path']} ({chunk['characters']} characters)")
        else:
            for stage, value in state["stages"].items():
                console.print(f"{stage}: {value}")
            pending = (
                [key for key, value in state["sections"].items() if value == "pending"]
                if state["stages"]["mapped"] == "done"
                else []
            )
            if pending:
                console.print("Pending sections: " + ", ".join(pending))
            for issue in issues:
                console.print(f"[yellow]![/yellow] {issue}")
            if issues:
                console.print("Next: correct the validation issues above and rerun process.")
            elif state["stages"]["mapped"] != "done":
                console.print("Next: create paper-map.md and paper-map.json from structure.json.")
            elif pending:
                console.print(
                    "Next: read one section chunk and write its evidence/<section-id>.jsonl."
                )
            elif state["stages"]["cards_built"] != "done":
                console.print("Next: build method-card.md and result-card.md from evidence.jsonl.")
            elif state["stages"]["paper_synthesized"] != "done":
                console.print("Next: build paper-note.md from validated cards and evidence.")
            elif state["stages"]["literature_published"] != "done":
                console.print("Next: run paperflow process <paper> --publish-note.")
            elif state["stages"]["knowledge_integrated"] != "done":
                console.print(
                    "Next: review existing knowledge notes and record knowledge-integration.md."
                )
        if issues:
            raise typer.Exit(1)
    except (OSError, ValueError) as error:
        console.print(f"[red]✗[/red] {error}")
        raise typer.Exit(1) from error


@app.command()
def migrate(
    paper: Annotated[str, typer.Argument(help="One synced Zotero key or citekey")],
    vault: Annotated[Path | None, typer.Option("--vault", help="Vault or config path")] = None,
) -> None:
    """Capture legacy notes once and reconcile one paper without rewriting them."""
    config = _get_config(vault)
    try:
        directory, result = reconcile_legacy(config, paper)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        console.print(f"[red]✗[/red] {error}")
        raise typer.Exit(1) from error
    console.print(f"Migration: {result['status']} · {directory}")
    for issue in result["issues"]:
        console.print(f"[yellow]![/yellow] {issue}")
    if result["duplicate_candidates"]:
        console.print("Duplicate Zotero candidates need manual review.")
    if result["issues"]:
        raise typer.Exit(1)


@app.command()
def status(
    vault: Annotated[Path | None, typer.Option("--vault", help="Vault or config path")] = None,
) -> None:
    """Show the useful state of your research workspace at a glance."""
    config = _get_config(vault)
    manifest = load_manifest(config)
    records = manifest.get("items", {})
    pending: int | None = None
    annotations: int | None = None
    zotero_total: int | None = None
    synced = len(records)
    try:
        items, collections = fetch_snapshot(config.collection_keys, timeout=30)
        zotero_total = len(items)
        synced = sum(item["zotero_key"] in records for item in items)
        pending, annotations, missing = changes(items, manifest, config)
    except ZoteroUnavailable:
        collections = []
        missing = sum(
            1
            for entry in records.values()
            if not (config.vault / entry.get("note_path", "")).exists()
        )

    table = Table.grid(padding=(0, 3))
    table.add_column(style="bold cyan", width=14)
    table.add_column()
    table.add_row(
        "Zotero", _paper_count(zotero_total) if zotero_total is not None else "Unavailable"
    )
    table.add_row("Scope", _scope_text(config.collection_keys, collections))
    table.add_row("Vault", str(config.vault))
    detail = f"{synced:,} synced"
    if pending is not None:
        detail += f" · {pending:,} pending"
    if missing:
        detail += f" · {missing:,} missing"
    table.add_row("Literature", detail)
    table.add_row("Annotations", f"{annotations:,} new" if annotations is not None else "—")
    counts = triage_summary(config)
    triage_detail = f"{counts['carded']:,} triaged"
    if counts["high"] or counts["recommended"]:
        triage_detail += f" · {counts['high']:,} high · {counts['recommended']:,} deep"
    if counts["pending"]:
        triage_detail += f" · {counts['pending']:,} pending"
    table.add_row("Triage", triage_detail)
    table.add_row("Last sync", _relative_time(manifest.get("last_sync_at")))
    console.print(Panel(table, title="[bold]PaperFlow[/bold]", expand=False))
    if pending:
        console.print("\nRun: [bold]paperflow sync[/bold]")
    elif counts["pending"]:
        console.print("\nRun: [bold]paperflow triage[/bold]")


@app.command()
def doctor(
    vault: Annotated[Path | None, typer.Option("--vault", help="Vault or config path")] = None,
) -> None:
    """Check what PaperFlow needs and explain how to fix it."""
    problems = 0
    try:
        config = load_config(vault)
        console.print("[green]✓[/green] Config valid")
    except (FileNotFoundError, KeyError, OSError, ValueError) as error:
        console.print(f"[red]✗[/red] Config invalid — {error}")
        console.print("  Run: [bold]paperflow init[/bold]")
        raise typer.Exit(1) from error

    if config.vault.is_dir():
        console.print(f"[green]✓[/green] Vault found — {config.vault}")
    else:
        problems += 1
        console.print(f"[red]✗[/red] Vault not found — {config.vault}")
        console.print("  Run [bold]paperflow init <vault>[/bold] to select it again.")

    ok, detail = ping()
    if ok:
        console.print("[green]✓[/green] Zotero reachable")
    else:
        problems += 1
        console.print("[red]✗[/red] Cannot reach Zotero")
        console.print("  Open Zotero. If this is your first run, use: [bold]zot init[/bold]")
        if detail:
            console.print(f"  [dim]{detail.splitlines()[-1]}[/dim]")

    if ok and config.collection_keys:
        try:
            available = {collection.key for collection in list_collections()}
            missing_keys = [key for key in config.collection_keys if key not in available]
            if missing_keys:
                problems += 1
                console.print("[red]✗[/red] A selected Zotero collection no longer exists")
                console.print("  Run [bold]paperflow init[/bold] to choose the scope again.")
            else:
                console.print("[green]✓[/green] Collection scope valid")
        except ZoteroUnavailable:
            pass

    for command, label in (("codex", "Codex"), ("git", "Git")):
        if command_available(command):
            console.print(f"[green]✓[/green] {label} found")
        else:
            problems += 1
            console.print(f"[red]✗[/red] {label} not found on PATH")

    if problems:
        raise typer.Exit(1)
