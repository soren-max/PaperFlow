from __future__ import annotations

import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .config import Config, load_config, load_manifest, save_manifest, write_config
from .discovery import command_available, discover_vaults, zotero_profile_found
from .sync import changes, synchronize
from .zotero import ZoteroUnavailable, fetch_library, ping

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

VAULT_AGENTS = """# PaperFlow Vault

This is a personal research knowledge base.

- `01-Literature/` contains source-grounded Zotero literature notes. Preserve PaperFlow managed blocks and `My Notes`.
- `02-Concepts/` contains durable ideas connected across papers.
- `03-Synthesis/` contains cross-paper comparisons, arguments, and writing material.
- `04-Questions/` contains open research questions and resolved answers worth keeping.

Treat Literature as evidence. Use Codex to turn that evidence into Concepts and Synthesis. Mark uncertainty explicitly and prefer Obsidian links between durable notes.
"""


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
    config = Config(vault=vault)
    for folder in ("01-Literature", "02-Concepts", "03-Synthesis", "04-Questions"):
        (vault / folder).mkdir(exist_ok=True)
    agents = vault / "AGENTS.md"
    if not agents.exists():
        agents.write_text(VAULT_AGENTS, encoding="utf-8")
    write_config(config)
    if not config.manifest_path.exists():
        save_manifest(config, {"version": 1, "last_sync_at": None, "items": {}})

    console.print(Panel.fit(f"[bold green]PaperFlow is ready[/bold green]\n{vault}"))
    console.print("\nCreated Literature, Concepts, Synthesis, and Questions folders.")
    ok, _ = ping(timeout=5)
    if ok:
        console.print("[green]✓[/green] Zotero is connected")
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
        items = fetch_library()
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
    try:
        items = fetch_library(timeout=30)
        zotero_total = len(items)
        pending, annotations, missing = changes(items, manifest, config)
    except ZoteroUnavailable:
        missing = sum(
            1
            for entry in records.values()
            if not (config.vault / entry.get("note_path", "")).exists()
        )

    table = Table.grid(padding=(0, 3))
    table.add_column(style="bold cyan", width=14)
    table.add_column()
    table.add_row(
        "Zotero", f"{zotero_total:,} papers" if zotero_total is not None else "Unavailable"
    )
    table.add_row("Vault", str(config.vault))
    detail = f"{len(records):,} synced"
    if pending is not None:
        detail += f" · {pending:,} pending"
    if missing:
        detail += f" · {missing:,} missing"
    table.add_row("Literature", detail)
    table.add_row("Annotations", f"{annotations:,} new" if annotations is not None else "—")
    table.add_row("Last sync", _relative_time(manifest.get("last_sync_at")))
    console.print(Panel(table, title="[bold]PaperFlow[/bold]", expand=False))
    if pending:
        console.print("\nRun: [bold]paperflow sync[/bold]")


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

    for command, label in (("codex", "Codex"), ("git", "Git")):
        if command_available(command):
            console.print(f"[green]✓[/green] {label} found")
        else:
            problems += 1
            console.print(f"[red]✗[/red] {label} not found on PATH")

    if problems:
        raise typer.Exit(1)
