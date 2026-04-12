"""Performance test: grill-yourself completes in <60s for a mock scenario (T071).

Creates a mock 5-file, 200-line diff scenario and asserts the grill-yourself
logic (without LLM calls) completes quickly.
"""

from __future__ import annotations

import time

import pytest

from agent_power_pack.grill.triggers import should_grill
from agent_power_pack.grill.config import GrillTriggerConfig
from agent_power_pack.grill.transcript import GrillTranscript, render_markdown
from agent_power_pack.grill.yourself import generate_questions


@pytest.mark.perf
class TestGrillYourselfPerformance:
    def test_grill_yourself_under_60s(self) -> None:
        """Full grill-yourself pipeline (no LLM) must complete in <60 seconds."""
        # Build a mock 5-file, 200-line numstat
        files = [
            (25, 15, "src/agent_power_pack/grill/config.py"),
            (40, 20, "src/agent_power_pack/grill/triggers.py"),
            (30, 10, "src/agent_power_pack/grill/transcript.py"),
            (20, 15, "src/agent_power_pack/grill/yourself.py"),
            (15, 10, "tests/unit/test_grill_triggers.py"),
        ]
        numstat_lines = [f"{a}\t{d}\t{fp}" for a, d, fp in files]
        numstat = "\n".join(numstat_lines)
        filepaths = [fp for _, _, fp in files]
        total_lines = sum(a + d for a, d, _ in files)

        start = time.monotonic()

        # Step 1: Evaluate trigger
        config = GrillTriggerConfig(max_lines=200, max_files=5)
        decision = should_grill(numstat, config=config)

        # Step 2: Generate questions
        questions = generate_questions(filepaths, total_lines)

        # Step 3: Build transcript
        transcript = GrillTranscript(
            spec_id="PERF-TEST",
            questions=questions,
            summary=f"Performance test: {len(questions)} questions generated.",
        )

        # Step 4: Render markdown
        md = render_markdown(transcript)

        elapsed = time.monotonic() - start

        assert elapsed < 60.0, f"Grill-yourself took {elapsed:.1f}s (limit: 60s)"
        assert decision.lines_changed == total_lines
        assert len(questions) >= 5
        assert "# Grill-Yourself Transcript" in md
