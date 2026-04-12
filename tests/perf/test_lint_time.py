"""Performance test: lint a 500-line AGENTS.md with 50 Make targets under 2s (T045)."""

from __future__ import annotations

from pathlib import Path

import pytest

from agent_power_pack.linter.agents_md import lint_agents_md


def _build_large_agents_md(num_targets: int = 50, total_lines: int = 500) -> str:
    """Build a large AGENTS.md with the required sections and many targets."""
    sections = [
        "## CI/CD Protocol\n\nRun CI pipeline.\n",
        "## Quality Gates\n\nAll gates must pass.\n",
        "## Troubleshooting\n\nCheck logs for errors.\n",
        "## Available Commands\n\n",
        "## Docker Conventions\n\n`docker compose up -d mcp`\n",
        "## Deployment\n\nDeploy via compose.\n",
    ]

    # Add make targets to Available Commands
    target_lines = []
    for i in range(num_targets):
        target_lines.append(f"- `make target-{i:03d}` — does thing {i}")
    sections[3] += "\n".join(target_lines) + "\n"

    content = "# AGENTS.md\n\n" + "\n".join(sections)

    # Pad to reach total_lines
    current_lines = len(content.splitlines())
    if current_lines < total_lines:
        padding = "\n".join(
            f"<!-- padding line {i} -->" for i in range(total_lines - current_lines)
        )
        content += "\n" + padding + "\n"

    return content


@pytest.mark.perf
def test_lint_500_lines_50_targets(tmp_path: Path) -> None:
    """Lint a 500-line AGENTS.md with 50 Make targets in under 2 seconds."""
    agents_md = tmp_path / "AGENTS.md"
    content = _build_large_agents_md(num_targets=50, total_lines=500)
    agents_md.write_text(content)

    # Create a Makefile with all 50 targets
    makefile_lines = []
    for i in range(50):
        makefile_lines.append(f"target-{i:03d}:\n\t@echo ok\n")
    makefile = tmp_path / "Makefile"
    makefile.write_text("\n".join(makefile_lines))

    result = lint_agents_md(tmp_path)

    assert result.duration_ms < 2000, f"Lint took {result.duration_ms}ms, expected < 2000ms"
    assert result.status == "pass"
