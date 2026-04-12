"""Integration tests for the Claude Code adapter (T029).

Golden-file assertions: load fixture manifests, install to tmpdir, assert
the resulting file tree matches tests/integration/golden/claude/ byte-for-byte,
assert InstallReport.files_written matches, assert idempotence on rerun.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from agent_power_pack.manifest.loader import load_all_manifests
from adapters.claude import ClaudeAdapter

FIXTURES = Path(__file__).parent / "fixtures" / "manifests"
GOLDEN = Path(__file__).parent / "golden" / "claude"


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
def adapter() -> ClaudeAdapter:
    return ClaudeAdapter()


@pytest.mark.integration
class TestClaudeAdapter:
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
        assert len(report2.files_skipped) == len(manifests), "All files should be skipped"

    def test_duration_tracked(self, tmp_path: Path, manifests, adapter):
        """InstallReport.duration_ms should be a non-negative integer."""
        report = adapter.install(manifests, tmp_path)
        assert report.duration_ms >= 0

    def test_no_errors(self, tmp_path: Path, manifests, adapter):
        """A clean install should produce no validation errors."""
        report = adapter.install(manifests, tmp_path)
        assert report.ok
        assert len(report.validation_errors) == 0
