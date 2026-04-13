"""Integration tests for the project:init wizard (T093)."""

from __future__ import annotations

from pathlib import Path

import pytest

from agent_power_pack.cpp_init.wizard import run_wizard


@pytest.mark.integration
class TestWizardHappyPath:
    """Test the wizard creates all expected files."""

    def test_creates_all_files(self, tmp_path: Path) -> None:
        report = run_wizard(
            tmp_path / "my-project",
            skip_plane=True,
            skip_wikijs=True,
        )

        assert (report.target_dir / "AGENTS.md").exists()
        assert (report.target_dir / "Makefile").exists()
        assert (report.target_dir / ".gitignore").exists()
        assert (report.target_dir / ".specify" / "grill-triggers.yaml").exists()

        assert len(report.files_created) == 4

    def test_agents_md_has_six_sections(self, tmp_path: Path) -> None:
        report = run_wizard(
            tmp_path / "my-project",
            skip_plane=True,
            skip_wikijs=True,
        )

        content = (report.target_dir / "AGENTS.md").read_text()
        required_sections = [
            "## CI/CD Protocol",
            "## Quality Gates",
            "## Troubleshooting",
            "## Available Commands",
            "## Docker Conventions",
            "## Deployment",
        ]
        for section in required_sections:
            assert section in content, f"Missing section: {section}"

    def test_makefile_has_required_targets(self, tmp_path: Path) -> None:
        report = run_wizard(
            tmp_path / "my-project",
            skip_plane=True,
            skip_wikijs=True,
        )

        content = (report.target_dir / "Makefile").read_text()
        for target in ["lint", "test", "verify", "install", "mcp-up", "mcp-down"]:
            assert f"{target}:" in content, f"Missing Makefile target: {target}"

    def test_framework_recorded(self, tmp_path: Path) -> None:
        report = run_wizard(
            tmp_path / "my-project",
            framework="fastapi",
            skip_plane=True,
            skip_wikijs=True,
        )
        assert report.framework == "fastapi"


@pytest.mark.integration
class TestWizardSkipPlane:
    """Test the wizard with --skip-plane."""

    def test_plane_not_configured(self, tmp_path: Path) -> None:
        report = run_wizard(
            tmp_path / "my-project",
            skip_plane=True,
            skip_wikijs=True,
        )
        assert report.plane_configured is False
        assert report.plane_probe is None

    def test_files_still_created(self, tmp_path: Path) -> None:
        report = run_wizard(
            tmp_path / "my-project",
            skip_plane=True,
            skip_wikijs=True,
        )
        assert len(report.files_created) == 4


@pytest.mark.integration
class TestWizardSkipWikijs:
    """Test the wizard with --skip-wikijs."""

    def test_wikijs_not_configured(self, tmp_path: Path) -> None:
        report = run_wizard(
            tmp_path / "my-project",
            skip_plane=True,
            skip_wikijs=True,
        )
        assert report.wikijs_configured is False
        assert report.wikijs_probe is None

    def test_files_still_created(self, tmp_path: Path) -> None:
        report = run_wizard(
            tmp_path / "my-project",
            skip_plane=True,
            skip_wikijs=True,
        )
        assert len(report.files_created) == 4


@pytest.mark.integration
class TestWizardSkipOpenaiDocs:
    """Test the wizard with --skip-openai-docs."""

    def test_openai_docs_not_configured(self, tmp_path: Path) -> None:
        report = run_wizard(
            tmp_path / "my-project",
            skip_plane=True,
            skip_wikijs=True,
            skip_openai_docs=True,
        )
        assert report.openai_docs_configured is False
        assert report.openai_docs_probe is None

    def test_openai_docs_skipped_without_url(self, tmp_path: Path) -> None:
        report = run_wizard(
            tmp_path / "my-project",
            skip_plane=True,
            skip_wikijs=True,
        )
        assert report.openai_docs_configured is False
        assert report.openai_docs_probe is None

    def test_files_still_created(self, tmp_path: Path) -> None:
        report = run_wizard(
            tmp_path / "my-project",
            skip_plane=True,
            skip_wikijs=True,
            skip_openai_docs=True,
        )
        assert len(report.files_created) == 4


@pytest.mark.integration
class TestWizardIdempotency:
    """Test running the wizard twice on the same directory."""

    def test_overwrites_existing_files(self, tmp_path: Path) -> None:
        target = tmp_path / "my-project"
        run_wizard(target, skip_plane=True, skip_wikijs=True)
        report = run_wizard(target, skip_plane=True, skip_wikijs=True)

        assert len(report.files_created) == 4
        assert (report.target_dir / "AGENTS.md").exists()
