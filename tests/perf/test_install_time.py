"""Performance test: make install RUNTIME=claude completes in <30s (T032).

Uses the real manifests directory to benchmark actual install throughput.
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from agent_power_pack.manifest.loader import load_all_manifests
from adapters.claude import ClaudeAdapter

REPO_ROOT = Path(__file__).parent.parent.parent
MANIFESTS_DIR = REPO_ROOT / "manifests"

# Skip if no manifests exist (e.g., CI without manifests checked out)
pytestmark = pytest.mark.skipif(
    not MANIFESTS_DIR.is_dir() or not list(MANIFESTS_DIR.rglob("*.yaml")),
    reason="No manifests directory found",
)


@pytest.mark.perf
class TestInstallPerformance:
    def test_claude_install_under_30s(self, tmp_path: Path):
        """Full catalog install into Claude layout must complete in <30 seconds."""
        manifests = load_all_manifests(MANIFESTS_DIR)
        adapter = ClaudeAdapter()

        start = time.monotonic()
        report = adapter.install(manifests, tmp_path)
        elapsed = time.monotonic() - start

        assert elapsed < 30.0, f"Install took {elapsed:.1f}s (limit: 30s)"
        assert report.ok
        assert len(report.files_written) > 0
