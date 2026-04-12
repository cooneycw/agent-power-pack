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
    step: str = typer.Argument(
        ..., help="Flow step: start, check, finish, auto, merge, deploy, etc."
    ),
    issue: str = typer.Argument(None, help="Issue number (required for some steps)."),
) -> None:
    """Run flow steps (start, check, finish, auto, merge, deploy)."""
    if step == "finish":
        import subprocess

        from agent_power_pack.grill.triggers import should_grill
        from agent_power_pack.grill.yourself import run_grill_yourself

        # Collect numstat diff against origin/main
        try:
            diff_result = subprocess.run(
                ["git", "diff", "--numstat", "origin/main...HEAD"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            numstat = diff_result.stdout.strip()
        except (subprocess.TimeoutExpired, FileNotFoundError):
            numstat = ""

        # Parse HEAD commit for grill-yourself trailer
        trailer: str | None = None
        try:
            msg_result = subprocess.run(
                ["git", "log", "-1", "--format=%B"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            for line in msg_result.stdout.strip().splitlines():
                stripped = line.strip().lower()
                if stripped.startswith("grill-yourself:"):
                    trailer = stripped.split(":", 1)[1].strip()
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        decision = should_grill(numstat, trailer=trailer)
        typer.echo(f"flow finish: {decision.reason}")

        if decision.should_fire:
            # Detect PR ref
            pr_ref: str | None = None
            try:
                pr_result = subprocess.run(
                    ["gh", "pr", "view", "--json", "number", "-q", ".number"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if pr_result.returncode == 0 and pr_result.stdout.strip():
                    pr_ref = f"#{pr_result.stdout.strip()}"
            except (subprocess.TimeoutExpired, FileNotFoundError):
                pass

            transcript = run_grill_yourself(pr_ref=pr_ref)
            typer.echo(f"Grill-yourself complete: {len(transcript.questions)} questions")
            typer.echo(f"Summary: {transcript.summary}")

            # Attach transcript to PR if possible
            if pr_ref:
                from agent_power_pack.grill.transcript import render_markdown

                md = render_markdown(transcript)
                try:
                    subprocess.run(
                        ["gh", "pr", "edit", "--body", md],
                        capture_output=True,
                        text=True,
                        timeout=10,
                    )
                    typer.echo(f"Transcript attached to PR {pr_ref}")
                except (subprocess.TimeoutExpired, FileNotFoundError):
                    typer.echo("Could not attach transcript to PR")
        else:
            typer.echo("Grill-yourself not triggered.")
    else:
        typer.echo(f"flow: step={step}, issue={issue} [stub]")


@app.command()
def grill(
    mode: str = typer.Argument(..., help="Grill mode: me, yourself."),
    plan: str = typer.Option(None, "--plan", "-p", help="Plan text to grill."),
    spec_id: str = typer.Option(None, "--spec-id", help="Spec ID for transcript filename."),
) -> None:
    """Run grill skills (me, yourself)."""
    if mode == "yourself":
        from agent_power_pack.grill.yourself import run_grill_yourself

        transcript = run_grill_yourself(plan=plan, spec_id=spec_id)
        typer.echo(f"Grill-yourself complete: {len(transcript.questions)} questions")
        typer.echo(f"Summary: {transcript.summary}")
    else:
        typer.echo(f"grill: mode={mode} [stub -- see Phase 7 for grill:me]")


@app.command()
def cicd(
    step: str = typer.Argument(
        ..., help="CICD step: init, woodpecker-checklist."
    ),
    pipeline_file: str = typer.Option(
        ".woodpecker.yml", "--file", "-f", help="Path to .woodpecker.yml."
    ),
    validate: bool = typer.Option(
        False, "--validate", help="Run in non-interactive validator mode."
    ),
    json_output: bool = typer.Option(False, "--json", help="Emit JSON output."),
    waive: list[str] = typer.Option(
        [], "--waive", "-w", help="Rule IDs to waive (repeatable)."
    ),
) -> None:
    """Run CI/CD tools (woodpecker-checklist, init)."""
    import json
    from pathlib import Path

    from rich.console import Console
    from rich.table import Table

    from agent_power_pack.cicd.woodpecker_checklist import (
        NON_WAIVABLE_RULES,
        load_pipeline,
        run_validator,
        validate_pipeline_file,
    )

    console = Console()

    if step == "woodpecker-checklist":
        path = Path(pipeline_file)
        if not path.exists():
            console.print(f"[red]Pipeline file not found: {path}[/red]")
            raise typer.Exit(code=1)

        waived = set(waive) if waive else None
        result = validate_pipeline_file(path, waived_rules=waived)

        if json_output:
            console.print(json.dumps(result.model_dump(), indent=2))
        else:
            table = Table(title="Woodpecker Checklist Results")
            table.add_column("Rule", style="bold")
            table.add_column("Status")
            table.add_column("Evidence")
            for r in result.rules:
                style = {"pass": "green", "fail": "red", "waived": "yellow"}[r.status]
                table.add_row(r.rule_id, f"[{style}]{r.status}[/{style}]", r.evidence or "")
            console.print(table)
            console.print(f"\nOverall: [{'red' if result.status == 'fail' else 'green'}]{result.status}[/]")

        if result.status == "fail":
            raise typer.Exit(code=1)

    elif step == "init":
        # FR-018: cicd:init invokes woodpecker-checklist in validator mode
        path = Path(pipeline_file)
        if not path.exists():
            console.print(f"[yellow]No pipeline file at {path} — generate one first.[/yellow]")
            raise typer.Exit(code=1)

        result = validate_pipeline_file(path)
        non_waivable_failures = [
            r for r in result.failed_rules if r.rule_id in NON_WAIVABLE_RULES
        ]

        if non_waivable_failures:
            console.print("[red]cicd:init BLOCKED — non-waivable checklist failures:[/red]")
            for r in non_waivable_failures:
                console.print(f"  [red]{r.rule_id}[/red]: {r.evidence}")
            console.print(
                "\n[yellow]Fix the above issues before finalizing CI/CD setup.[/yellow]"
            )
            raise typer.Exit(code=1)

        if result.status == "fail":
            console.print("[yellow]cicd:init WARNING — waivable checklist failures:[/yellow]")
            for r in result.failed_rules:
                console.print(f"  [yellow]{r.rule_id}[/yellow]: {r.evidence}")
            console.print("\nThese can be waived. Pipeline file accepted with warnings.")
        else:
            console.print("[green]cicd:init — all checklist items pass. Pipeline accepted.[/green]")

    else:
        console.print(f"[red]Unknown cicd step '{step}'. Valid: init, woodpecker-checklist[/red]")
        raise typer.Exit(code=1)


def main() -> None:
    """Entry point for the agent-power-pack CLI."""
    app()
