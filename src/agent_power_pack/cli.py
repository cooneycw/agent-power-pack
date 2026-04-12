"""CLI entrypoint for agent-power-pack using typer.

Subcommands are placeholders — bodies are filled in during user-story phases.
"""

from __future__ import annotations

import typer

from agent_power_pack.logging import configure_logging

app = typer.Typer(
    name="agent-power-pack",
    help="Universal agentic power pack for Claude Code, Codex CLI, Gemini CLI, and Cursor.",
    no_args_is_help=True,
)


@app.callback()
def _main(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable debug logging."),
) -> None:
    """Global options applied before any subcommand."""
    import logging

    configure_logging(level=logging.DEBUG if verbose else logging.INFO)


@app.command()
def install(
    runtime: str = typer.Argument(..., help="Target runtime: claude-code, codex-cli, gemini-cli, cursor."),
    target_dir: str = typer.Option(".", "--target-dir", "-d", help="Repo root to install into."),
    mode: str = typer.Option("project", "--mode", "-m", help="Install mode: project or user."),
    manifests_dir: str = typer.Option("manifests", "--manifests", help="Path to manifests directory."),
    json_output: bool = typer.Option(False, "--json", help="Emit JSON instead of human table."),
) -> None:
    """Install skill catalog into a runtime's native layout."""
    from pathlib import Path

    from rich.console import Console
    from rich.table import Table

    from adapters import AdapterNotImplemented
    from agent_power_pack.manifest.loader import load_all_manifests

    console = Console()

    # Adapter registry — keyed by runtime_id
    adapter_map: dict[str, type] = {}
    try:
        from adapters.claude import ClaudeAdapter
        adapter_map["claude-code"] = ClaudeAdapter
    except ImportError:
        pass
    try:
        from adapters.codex import CodexAdapter
        adapter_map["codex-cli"] = CodexAdapter
    except ImportError:
        pass
    try:
        from adapters.gemini import GeminiStub
        adapter_map["gemini-cli"] = GeminiStub
    except ImportError:
        pass
    try:
        from adapters.cursor import CursorStub
        adapter_map["cursor"] = CursorStub
    except ImportError:
        pass

    if runtime not in adapter_map:
        valid = sorted(adapter_map.keys())
        console.print(f"[red]Unknown runtime '{runtime}'. Valid: {valid}[/red]")
        raise typer.Exit(code=1)

    target = Path(target_dir).resolve()
    manifests_path = Path(manifests_dir)
    if not manifests_path.is_absolute():
        manifests_path = target / manifests_path

    if not manifests_path.is_dir():
        console.print(f"[red]Manifests directory not found: {manifests_path}[/red]")
        raise typer.Exit(code=1)

    manifests = load_all_manifests(manifests_path)
    adapter = adapter_map[runtime]()

    try:
        report = adapter.install(manifests, target, mode=mode)
    except AdapterNotImplemented as exc:
        console.print(f"[yellow]{exc}[/yellow]")
        raise typer.Exit(code=1)

    if json_output:
        import json
        console.print(json.dumps({
            "runtime": runtime,
            "files_written": [str(p) for p in report.files_written],
            "files_skipped": [str(p) for p in report.files_skipped],
            "validation_errors": report.validation_errors,
            "duration_ms": report.duration_ms,
        }, indent=2))
    else:
        table = Table(title=f"Install Report — {runtime}")
        table.add_column("Metric", style="bold")
        table.add_column("Value")
        table.add_row("Runtime", runtime)
        table.add_row("Files written", str(len(report.files_written)))
        table.add_row("Files skipped", str(len(report.files_skipped)))
        table.add_row("Errors", str(len(report.validation_errors)))
        table.add_row("Duration", f"{report.duration_ms}ms")
        console.print(table)
        if report.files_written:
            console.print("\n[green]Written:[/green]")
            for p in report.files_written:
                console.print(f"  {p}")
        if report.validation_errors:
            console.print("\n[red]Errors:[/red]")
            for e in report.validation_errors:
                console.print(f"  {e}")


@app.command()
def lint(
    target: str = typer.Argument("agents-md", help="What to lint (agents-md)."),
    json_output: bool = typer.Option(False, "--json", help="Emit structured JSON output."),
    fix: bool = typer.Option(False, "--fix", help="Auto-fix what can be fixed."),
) -> None:
    """Run linters (agents-md:lint)."""
    typer.echo(f"lint: target={target}, json={json_output}, fix={fix} [stub]")


@app.command()
def generate(
    target: str = typer.Argument(..., help="What to generate (e.g. claude-md, gemini-md, cursorrules)."),
) -> None:
    """Generate runtime-specific instruction files from AGENTS.md."""
    typer.echo(f"generate: target={target} [stub]")


@app.command()
def init(
    reconfigure: str = typer.Option(None, "--reconfigure", help="Reconfigure a specific integration (plane, wikijs)."),
) -> None:
    """Bootstrap a new project with guided Plane + Wiki.js setup."""
    typer.echo(f"init: reconfigure={reconfigure} [stub]")


@app.command()
def flow(
    step: str = typer.Argument(..., help="Flow step: start, check, finish, auto, merge, deploy, etc."),
    issue: str = typer.Argument(None, help="Issue number (required for some steps)."),
) -> None:
    """Run flow steps (start, check, finish, auto, merge, deploy)."""
    typer.echo(f"flow: step={step}, issue={issue} [stub]")


@app.command()
def grill(
    mode: str = typer.Argument(..., help="Grill mode: me, yourself."),
) -> None:
    """Run grill skills (me, yourself)."""
    typer.echo(f"grill: mode={mode} [stub]")


def main() -> None:
    """Entry point for the agent-power-pack CLI."""
    app()
