"""Performance test for project:init wizard (T094)."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from agent_power_pack.cpp_init.wizard import run_wizard


@pytest.mark.perf
class TestWizardPerformance:
    """Assert that the wizard completes quickly when probes are skipped."""

    def test_wizard_under_10s(self, tmp_path: Path) -> None:
        """run_wizard with skip_plane=True, skip_wikijs=True must complete in <10s."""
        start = time.monotonic()
        report = run_wizard(
            tmp_path / "perf-project",
            skip_plane=True,
            skip_wikijs=True,
        )
        elapsed = time.monotonic() - start

        assert elapsed < 10.0, f"Wizard took {elapsed:.1f}s (limit: 10s)"
        assert len(report.files_created) == 4
