"""Integration tests for the Codex CLI adapter (T030).

Golden-file assertions plus the ~/.codex/config.toml merge case.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from agent_power_pack.manifest.loader import load_all_manifests
from adapters.codex import CodexAdapter

FIXTURES = Path(__file__).parent / "fixtures" / "manifests"
GOLDEN = Path(__file__).parent / "golden" / "codex"


def _collect_files(root: Path) -> dict[str, str]:
    """Return {relative_path: content} for all files under root."""
    result: dict[str, str] = {}
    for f in sorted(root.rglob("*")):
        if f.is_file():
            result[str(f.relative_to(root))] = f.read_text()
    return result


@pytest.fixture
def manifests() -> list:
    return load_all_manifests(FIXTURES)


@pytest.fixture
def adapter() -> CodexAdapter:
    return CodexAdapter()


@pytest.mark.integration
class TestCodexAdapter:
    def test_file_tree_matches_golden(self, tmp_path: Path, manifests, adapter):
        """Installed file tree must match golden directory byte-for-byte."""
        adapter.install(manifests, tmp_path)

        actual = _collect_files(tmp_path)
        expected = _collect_files(GOLDEN)

        assert set(actual.keys()) == set(expected.keys()), (
            f"File tree mismatch.\n"
            f"  Extra:   {set(actual.keys()) - set(expected.keys())}\n"
            f"  Missing: {set(expected.keys()) - set(actual.keys())}"
        )

        for path in sorted(expected):
            assert actual[path] == expected[path], f"Content mismatch in {path}"

    def test_install_report_matches_tree(self, tmp_path: Path, manifests, adapter):
        """InstallReport.files_written must list every file created."""
        report = adapter.install(manifests, tmp_path)

        written_strs = {str(p) for p in report.files_written}
        actual_files = {str(p.relative_to(tmp_path)) for p in tmp_path.rglob("*") if p.is_file()}

        assert written_strs == actual_files

    def test_idempotence(self, tmp_path: Path, manifests, adapter):
        """Running install twice produces byte-identical results and reports skips."""
        adapter.install(manifests, tmp_path)
        first_files = _collect_files(tmp_path)

        report2 = adapter.install(manifests, tmp_path)
        second_files = _collect_files(tmp_path)

        assert first_files == second_files, "Files changed on second install"
        assert len(report2.files_written) == 0, "Second install should write nothing"
        assert len(report2.files_skipped) == len(manifests), (
            "All SKILL.md files should be skipped"
        )

    def test_duration_tracked(self, tmp_path: Path, manifests, adapter):
        report = adapter.install(manifests, tmp_path)
        assert report.duration_ms >= 0

    def test_no_errors(self, tmp_path: Path, manifests, adapter):
        report = adapter.install(manifests, tmp_path)
        assert report.ok

    def test_user_mode_config_toml_merge(self, tmp_path: Path, manifests, adapter):
        """User mode should merge MCP server registrations into config.toml."""
        fake_home = tmp_path / "home"
        fake_home.mkdir()
        codex_dir = fake_home / ".codex"
        codex_dir.mkdir()

        # Pre-existing config with user content that must be preserved
        config = codex_dir / "config.toml"
        config.write_text('[user]\nname = "test"\n')

        with patch("adapters.codex.Path.home", return_value=fake_home):
            adapter.install(manifests, fake_home, mode="user")

        assert config.exists()
        content = config.read_text()
        # User section preserved
        assert '[user]' in content
        assert 'name = "test"' in content
        # Our MCP sections added (only for manifests with mcp_tools)
        assert "agent-power-pack" in content

    def test_user_mode_config_toml_created_fresh(self, tmp_path: Path, manifests, adapter):
        """If config.toml doesn't exist, create it with only our sections."""
        fake_home = tmp_path / "home"
        fake_home.mkdir()

        with patch("adapters.codex.Path.home", return_value=fake_home):
            adapter.install(manifests, fake_home, mode="user")

        config = fake_home / ".codex" / "config.toml"
        assert config.exists()
        content = config.read_text()
        assert "agent-power-pack" in content

    def test_user_mode_config_toml_idempotent(self, tmp_path: Path, manifests, adapter):
        """Second user-mode install should not change config.toml."""
        fake_home = tmp_path / "home"
        fake_home.mkdir()

        with patch("adapters.codex.Path.home", return_value=fake_home):
            adapter.install(manifests, fake_home, mode="user")
            config = fake_home / ".codex" / "config.toml"
            first_content = config.read_text()

            adapter.install(manifests, fake_home, mode="user")
            second_content = config.read_text()

        assert first_content == second_content
