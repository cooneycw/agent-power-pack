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


_RUNTIME_ALIASES = {
    "claude": "claude-code",
    "codex": "codex-cli",
    "gemini": "gemini-cli",
}


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
    runtime = _RUNTIME_ALIASES.get(runtime, runtime)

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
    import json
    from pathlib import Path

    from rich.console import Console
    from rich.table import Table

    from agent_power_pack.linter.agents_md import lint_agents_md

    console = Console()

    if target != "agents-md":
        console.print(f"[red]Unknown lint target '{target}'. Valid: agents-md[/red]")
        raise typer.Exit(code=1)

    result = lint_agents_md(Path.cwd(), fix=fix)

    if json_output:
        console.print(json.dumps(result.model_dump(), indent=2))
    else:
        table = Table(title="AGENTS.md Lint")
        table.add_column("Rule", style="bold")
        table.add_column("Status")
        table.add_column("Subject")
        table.add_column("Message")
        for check in result.checks:
            style = {"pass": "green", "fail": "red", "warn": "yellow"}[check.status]
            table.add_row(
                check.rule_id,
                f"[{style}]{check.status}[/{style}]",
                check.subject or "",
                check.message,
            )
        console.print(table)
        console.print(
            f"\nOverall: [{'red' if result.status == 'fail' else 'green'}]{result.status}[/]"
        )

    if result.status == "fail":
        raise typer.Exit(code=1)


@app.command()
def docs(
    step: str = typer.Argument(..., help="Docs step: analyze."),
    project_name: str = typer.Option(None, "--project", "-p", help="Project name for Wiki.js namespace."),
    json_output: bool = typer.Option(False, "--json", help="Emit JSON output."),
) -> None:
    """Run documentation pipeline steps (analyze)."""
    import json
    from pathlib import Path

    from rich.console import Console
    from rich.table import Table

    console = Console()

    if step == "analyze":
        from agent_power_pack.docs.plan_generator import generate_plan, write_plan_yaml
        from agent_power_pack.docs.signal_detector import build_proposals, detect_signals
        from agent_power_pack.docs.theme_analyzer import analyze_theme, write_theme_yaml

        project_root = Path.cwd()
        theme_dir = project_root / "docs" / "theme"

        # Detect project name
        if not project_name:
            import subprocess

            try:
                result = subprocess.run(
                    ["git", "remote", "get-url", "origin"],
                    capture_output=True, text=True, timeout=5,
                )
                if result.returncode == 0:
                    project_name = result.stdout.strip().rstrip("/").split("/")[-1]
                    if project_name.endswith(".git"):
                        project_name = project_name[:-4]
            except (subprocess.TimeoutExpired, FileNotFoundError):
                pass
            if not project_name:
                project_name = project_root.name

        console.print(f"[bold]docs:analyze[/bold] — project: {project_name}")

        # Step 1: Analyze theme
        console.print("\n[bold]Theme Analysis[/bold]")
        theme = analyze_theme(theme_dir)
        theme_path = theme_dir / "theme.yaml"
        write_theme_yaml(theme, theme_path)
        console.print(f"  Written: {theme_path}")

        warnings = theme.get("_warnings", [])
        if warnings:
            for w in warnings:
                console.print(f"  [yellow]Warning: {w}[/yellow]")

        # Display theme summary
        colors = theme.get("colors", {})
        fonts = theme.get("fonts", {})
        console.print(f"  Primary color:  {colors.get('primary', 'N/A')}")
        console.print(f"  Heading font:   {fonts.get('heading', 'N/A')}")
        console.print(f"  Body font:      {fonts.get('body', 'N/A')}")
        if theme.get("logos"):
            console.print(f"  Logos:          {', '.join(theme['logos'])}")

        # Step 2: Detect signals
        console.print("\n[bold]Signal Detection[/bold]")
        signals = detect_signals(project_root)

        # Load wiki structure if available
        wiki_structure: dict | None = None  # type: ignore[type-arg]
        wiki_path = project_root / "docs" / "wiki-structure.yaml"
        if wiki_path.exists():
            from ruamel.yaml import YAML
            yaml = YAML()
            with open(wiki_path) as f:
                wiki_structure = yaml.load(f)

        proposals = build_proposals(signals, project_name, wiki_structure)

        if not proposals:
            console.print("  [yellow]No documentation signals detected.[/yellow]")
        else:
            table = Table(title=f"{len(proposals)} Artifacts Proposed")
            table.add_column("Type", style="bold")
            table.add_column("Model")
            table.add_column("Confidence")
            table.add_column("Depth")
            table.add_column("Signals")
            for p in proposals:
                table.add_row(
                    p.type,
                    p.model,
                    f"{p.confidence:.0%}",
                    p.depth,
                    ", ".join(p.source_signals[:3]) + ("..." if len(p.source_signals) > 3 else ""),
                )
            console.print(table)

        # Step 3: Generate plan
        plan_path = project_root / "docs" / "plan.yaml"
        plan = generate_plan(project_name, proposals, plan_path)
        write_plan_yaml(plan, plan_path)
        console.print(f"\n  Plan written: {plan_path}")
        console.print(f"  Artifacts:    {len(plan.get('artifacts', []))}")

        if json_output:
            console.print(json.dumps({
                "project": project_name,
                "theme_path": str(theme_path),
                "plan_path": str(plan_path),
                "artifacts": len(plan.get("artifacts", [])),
                "warnings": warnings,
            }, indent=2))

        console.print("\n[bold green]docs:analyze complete[/bold green]")
        console.print("  Next: review docs/plan.yaml, then run /docs:auto")

    else:
        console.print(f"[red]Unknown docs step '{step}'. Valid: analyze[/red]")
        raise typer.Exit(code=1)


@app.command()
def generate(
    target: str = typer.Argument(..., help="What to generate (e.g. claude-md, gemini-md, cursorrules)."),
) -> None:
    """Generate runtime-specific instruction files from AGENTS.md."""
    typer.echo(f"generate: target={target} [stub]")


@app.command()
def init(
    project_name: str = typer.Argument(None, help="Project directory name to create."),
    framework: str = typer.Option("generic", "--framework", "-f", help="Project framework."),
    skip_plane: bool = typer.Option(False, "--skip-plane", help="Skip Plane connectivity probe."),
    skip_wikijs: bool = typer.Option(False, "--skip-wikijs", help="Skip Wiki.js connectivity probe."),
    reconfigure: str = typer.Option(
        None, "--reconfigure", help="Re-run probe for a specific integration (plane, wikijs)."
    ),
    here: bool = typer.Option(False, "--here", help="Init in the current directory."),
) -> None:
    """Bootstrap a new project with guided Plane + Wiki.js setup."""
    from pathlib import Path

    from rich.console import Console

    from agent_power_pack.cpp_init.wizard import run_wizard

    console = Console()

    if reconfigure:
        _handle_reconfigure(reconfigure, console)
        return

    if here:
        target_dir = Path.cwd()
    elif project_name:
        target_dir = Path.cwd() / project_name
    else:
        console.print("[red]Provide a PROJECT_NAME or use --here.[/red]")
        raise typer.Exit(code=1)

    report = run_wizard(
        target_dir,
        framework=framework,
        skip_plane=skip_plane,
        skip_wikijs=skip_wikijs,
    )

    console.print(f"\n[bold green]Project initialized in {report.target_dir}[/bold green]")
    console.print(f"Framework: {report.framework}")
    console.print(f"Files created: {len(report.files_created)}")
    for f in report.files_created:
        console.print(f"  {f}")

    if report.plane_probe:
        status = "[green]OK[/green]" if report.plane_configured else "[red]FAILED[/red]"
        console.print(f"Plane: {status}")
    elif not skip_plane:
        console.print("Plane: [yellow]skipped (no credentials)[/yellow]")

    if report.wikijs_probe:
        status = "[green]OK[/green]" if report.wikijs_configured else "[red]FAILED[/red]"
        console.print(f"Wiki.js: {status}")
    elif not skip_wikijs:
        console.print("Wiki.js: [yellow]skipped (no credentials)[/yellow]")


def _handle_reconfigure(integration: str, console: object) -> None:
    """Re-run a probe for a specific integration."""
    from agent_power_pack.cpp_init.probes import probe_plane, probe_wikijs
    from agent_power_pack.secrets import get_secret

    if integration == "plane":
        url = get_secret("PLANE_URL")
        workspace = get_secret("PLANE_WORKSPACE")
        token = get_secret("PLANE_API_TOKEN")
        if not all([url, workspace, token]):
            console.print("[red]Missing Plane credentials in secrets.[/red]")  # type: ignore[union-attr]
            raise typer.Exit(code=1)
        result = probe_plane(url, workspace, token)  # type: ignore[arg-type]
        status = "[green]OK[/green]" if result.ok else f"[red]FAILED: {result.detail}[/red]"
        console.print(f"Plane probe: {status}")  # type: ignore[union-attr]
    elif integration == "wikijs":
        url = get_secret("WIKIJS_URL")
        token = get_secret("WIKIJS_API_TOKEN")
        if not all([url, token]):
            console.print("[red]Missing Wiki.js credentials in secrets.[/red]")  # type: ignore[union-attr]
            raise typer.Exit(code=1)
        result = probe_wikijs(url, token)  # type: ignore[arg-type]
        status = "[green]OK[/green]" if result.ok else f"[red]FAILED: {result.detail}[/red]"
        console.print(f"Wiki.js probe: {status}")  # type: ignore[union-attr]
    else:
        console.print(f"[red]Unknown integration '{integration}'. Valid: plane, wikijs[/red]")  # type: ignore[union-attr]
        raise typer.Exit(code=1)


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
