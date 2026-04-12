"""project:init wizard — scaffolding, probes, and guided configuration (T084)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from agent_power_pack.cpp_init.probes import ProbeResult, probe_plane, probe_wikijs
from agent_power_pack.logging import get_logger

log = get_logger("cpp_init.wizard")

_AGENTS_MD_TEMPLATE = """\
# AGENTS.md

Project guidelines for AI-powered development agents.

## CI/CD Protocol

- All changes must go through pull requests.
- CI must pass before merge.
- Use `make verify` to run the full pre-merge check locally.

## Quality Gates

- Linting: `make lint`
- Tests: `make test`
- Full verification: `make verify`

## Troubleshooting

- If MCP tools are unavailable, check `make mcp-up` and container logs.
- If secrets fail, run `agent-power-pack secrets:health` to diagnose tiers.

## Available Commands

| Command | Description |
|---------|-------------|
| `make lint` | Run linters |
| `make test` | Run test suite |
| `make verify` | Full pre-merge check |
| `make install` | Install dependencies |
| `make mcp-up` | Start MCP container |
| `make mcp-down` | Stop MCP container |

## Docker Conventions

- Use `compose.yaml` for local dev services.
- MCP tools run inside a single container (see `make mcp-up`).

## Deployment

- Merge to `main` triggers CI/CD pipeline.
- Use `flow:deploy` for production deployments.
"""

_MAKEFILE_TEMPLATE = """\
.PHONY: lint test verify install mcp-up mcp-down

lint:
\t@echo "Running linters..."
\tuv run ruff check .

test:
\t@echo "Running tests..."
\tuv run pytest tests/ -v

verify: lint test
\t@echo "All checks passed."

install:
\t@echo "Installing dependencies..."
\tuv sync

mcp-up:
\t@echo "Starting MCP container..."
\tdocker compose up -d

mcp-down:
\t@echo "Stopping MCP container..."
\tdocker compose down
"""

_GITIGNORE_TEMPLATE = """\
# Python
__pycache__/
*.py[cod]
*$py.class
*.egg-info/
dist/
build/
.eggs/

# Virtual environments
.venv/
venv/

# IDE
.idea/
.vscode/
*.swp
*.swo

# Environment
.env
.env.local

# OS
.DS_Store
Thumbs.db

# Docker
docker-compose.override.yml
"""

_GRILL_TRIGGERS_TEMPLATE = """\
# .specify/grill-triggers.yaml
# Controls when grill-yourself fires automatically.

thresholds:
  lines_changed: 300
  files_changed: 10

skip_patterns:
  - "*.lock"
  - "*.generated.*"
  - "docs/**"

trailer_override: true
"""


@dataclass
class WizardReport:
    """Result of running the project:init wizard."""

    target_dir: Path
    framework: str
    files_created: list[Path] = field(default_factory=list)
    plane_configured: bool = False
    wikijs_configured: bool = False
    plane_probe: ProbeResult | None = None
    wikijs_probe: ProbeResult | None = None


def run_wizard(
    target_dir: Path,
    *,
    framework: str = "generic",
    skip_plane: bool = False,
    skip_wikijs: bool = False,
    plane_url: str | None = None,
    plane_workspace: str | None = None,
    plane_token: str | None = None,
    wikijs_url: str | None = None,
    wikijs_token: str | None = None,
) -> WizardReport:
    """Run the project:init wizard.

    Scaffolds project files and optionally probes Plane / Wiki.js.
    Does NOT prompt for user input — all config is passed as parameters.
    """
    report = WizardReport(target_dir=target_dir, framework=framework)

    target_dir.mkdir(parents=True, exist_ok=True)

    # Scaffold AGENTS.md
    agents_md = target_dir / "AGENTS.md"
    agents_md.write_text(_AGENTS_MD_TEMPLATE)
    report.files_created.append(agents_md)
    log.info("created AGENTS.md", path=str(agents_md))

    # Scaffold Makefile
    makefile = target_dir / "Makefile"
    makefile.write_text(_MAKEFILE_TEMPLATE)
    report.files_created.append(makefile)
    log.info("created Makefile", path=str(makefile))

    # Scaffold .gitignore
    gitignore = target_dir / ".gitignore"
    gitignore.write_text(_GITIGNORE_TEMPLATE)
    report.files_created.append(gitignore)
    log.info("created .gitignore", path=str(gitignore))

    # Scaffold .specify/grill-triggers.yaml
    specify_dir = target_dir / ".specify"
    specify_dir.mkdir(parents=True, exist_ok=True)
    grill_triggers = specify_dir / "grill-triggers.yaml"
    grill_triggers.write_text(_GRILL_TRIGGERS_TEMPLATE)
    report.files_created.append(grill_triggers)
    log.info("created grill-triggers.yaml", path=str(grill_triggers))

    # Probe Plane
    if not skip_plane and plane_url and plane_workspace and plane_token:
        probe = probe_plane(plane_url, plane_workspace, plane_token)
        report.plane_probe = probe
        report.plane_configured = probe.ok
        log.info("plane probe", ok=probe.ok, detail=probe.detail)
    elif not skip_plane:
        log.info("plane probe skipped — missing credentials")

    # Probe Wiki.js
    if not skip_wikijs and wikijs_url and wikijs_token:
        probe = probe_wikijs(wikijs_url, wikijs_token)
        report.wikijs_probe = probe
        report.wikijs_configured = probe.ok
        log.info("wikijs probe", ok=probe.ok, detail=probe.detail)
    elif not skip_wikijs:
        log.info("wikijs probe skipped — missing credentials")

    return report
