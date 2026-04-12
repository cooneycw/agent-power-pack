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
) -> None:
    """Install skill catalog into a runtime's native layout."""
    typer.echo(f"install: runtime={runtime}, target_dir={target_dir}, mode={mode} [stub]")


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
