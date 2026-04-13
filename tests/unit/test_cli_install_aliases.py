"""CLI install runtime alias coverage."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from agent_power_pack.cli import app


runner = CliRunner()


def test_install_accepts_codex_alias(tmp_path: Path) -> None:
    manifests = tmp_path / "manifests"
    manifests.mkdir()
    (manifests / "demo.yaml").write_text(
        """name: demo
family: demo
description: demo skill
triggers:
  - demo
runtimes:
  - codex-cli
order: 10
prompt: |
  hello
"""
    )

    result = runner.invoke(
        app,
        [
            "install",
            "codex",
            "--target-dir",
            str(tmp_path),
            "--manifests",
            str(manifests),
        ],
    )

    assert result.exit_code == 0, result.stdout
    assert (tmp_path / ".agents" / "skills" / "demo" / "SKILL.md").exists()
