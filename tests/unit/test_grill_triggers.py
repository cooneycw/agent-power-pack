"""Unit tests for grill triggers, config, and transcript (T070).

Covers: should_grill() threshold logic, trailer overrides, exclude_globs,
GrillTriggerConfig YAML loading + defaults, GrillTranscript + render_markdown.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from textwrap import dedent

from agent_power_pack.grill.config import GrillTriggerConfig, load_grill_config
from agent_power_pack.grill.transcript import GrillQA, GrillTranscript, render_markdown
from agent_power_pack.grill.triggers import should_grill


def _make_numstat(files: list[tuple[int, int, str]]) -> str:
    """Build a git diff --numstat string from (added, deleted, filepath) tuples."""
    lines = []
    for added, deleted, fp in files:
        lines.append(f"{added}\t{deleted}\t{fp}")
    return "\n".join(lines)


class TestGrillTriggerConfig:
    """Tests for GrillTriggerConfig model and YAML loader."""

    def test_defaults(self) -> None:
        cfg = GrillTriggerConfig()
        assert cfg.max_lines == 200
        assert cfg.max_files == 5
        assert cfg.exclude_globs == []

    def test_custom_values(self) -> None:
        cfg = GrillTriggerConfig(max_lines=100, max_files=3, exclude_globs=["*.md"])
        assert cfg.max_lines == 100
        assert cfg.max_files == 3
        assert cfg.exclude_globs == ["*.md"]

    def test_load_from_yaml(self, tmp_path: Path) -> None:
        config_file = tmp_path / "grill-triggers.yaml"
        config_file.write_text(dedent("""\
            max_lines: 300
            max_files: 10
            exclude_globs:
              - "*.lock"
              - "vendor/*"
        """))
        cfg = load_grill_config(config_file)
        assert cfg.max_lines == 300
        assert cfg.max_files == 10
        assert cfg.exclude_globs == ["*.lock", "vendor/*"]

    def test_load_missing_file_returns_defaults(self, tmp_path: Path) -> None:
        cfg = load_grill_config(tmp_path / "nonexistent.yaml")
        assert cfg.max_lines == 200
        assert cfg.max_files == 5

    def test_load_empty_file_returns_defaults(self, tmp_path: Path) -> None:
        config_file = tmp_path / "empty.yaml"
        config_file.write_text("")
        cfg = load_grill_config(config_file)
        assert cfg.max_lines == 200
        assert cfg.max_files == 5


class TestShouldGrill:
    """Tests for should_grill() threshold evaluator."""

    def test_below_threshold_no_fire(self) -> None:
        numstat = _make_numstat([(50, 30, "src/foo.py"), (10, 5, "src/bar.py")])
        config = GrillTriggerConfig(max_lines=200, max_files=5)
        decision = should_grill(numstat, config=config)
        assert decision.should_fire is False
        assert decision.lines_changed == 95
        assert decision.files_changed == 2

    def test_above_max_lines_fires(self) -> None:
        numstat = _make_numstat([(150, 60, "src/big.py")])
        config = GrillTriggerConfig(max_lines=200, max_files=5)
        decision = should_grill(numstat, config=config)
        assert decision.should_fire is True
        assert "Lines changed" in decision.reason
        assert decision.lines_changed == 210

    def test_above_max_files_fires(self) -> None:
        files = [(5, 5, f"src/file{i}.py") for i in range(6)]
        numstat = _make_numstat(files)
        config = GrillTriggerConfig(max_lines=200, max_files=5)
        decision = should_grill(numstat, config=config)
        assert decision.should_fire is True
        assert "Files changed" in decision.reason
        assert decision.files_changed == 6

    def test_exactly_at_boundary_no_fire(self) -> None:
        """Thresholds are 'exceeds', not 'equals'."""
        # Exactly 200 lines
        numstat = _make_numstat([(100, 100, "src/exact.py")])
        config = GrillTriggerConfig(max_lines=200, max_files=5)
        decision = should_grill(numstat, config=config)
        assert decision.should_fire is False

        # Exactly 5 files
        files = [(5, 5, f"src/f{i}.py") for i in range(5)]
        numstat = _make_numstat(files)
        decision = should_grill(numstat, config=config)
        assert decision.should_fire is False

    def test_trailer_force_always_fires(self) -> None:
        numstat = _make_numstat([(1, 1, "README.md")])
        config = GrillTriggerConfig(max_lines=200, max_files=5)
        decision = should_grill(numstat, config=config, trailer="force")
        assert decision.should_fire is True
        assert "force" in decision.reason.lower()

    def test_trailer_skip_always_suppresses(self) -> None:
        # Even a massive diff should be suppressed
        numstat = _make_numstat([(500, 500, f"src/f{i}.py") for i in range(20)])
        config = GrillTriggerConfig(max_lines=200, max_files=5)
        decision = should_grill(numstat, config=config, trailer="skip")
        assert decision.should_fire is False
        assert "skip" in decision.reason.lower()

    def test_exclude_globs_filters_files(self) -> None:
        numstat = _make_numstat([
            (150, 60, "src/main.py"),
            (500, 500, "poetry.lock"),
        ])
        config = GrillTriggerConfig(
            max_lines=200, max_files=5, exclude_globs=["*.lock"]
        )
        decision = should_grill(numstat, config=config)
        # Only src/main.py counts: 210 lines > 200
        assert decision.should_fire is True
        assert decision.lines_changed == 210
        assert decision.files_changed == 1

    def test_exclude_globs_can_drop_below_threshold(self) -> None:
        numstat = _make_numstat([
            (50, 30, "src/main.py"),
            (500, 500, "poetry.lock"),
        ])
        config = GrillTriggerConfig(
            max_lines=200, max_files=5, exclude_globs=["*.lock"]
        )
        decision = should_grill(numstat, config=config)
        assert decision.should_fire is False
        assert decision.lines_changed == 80

    def test_empty_diff_no_fire(self) -> None:
        decision = should_grill("", config=GrillTriggerConfig())
        assert decision.should_fire is False
        assert decision.lines_changed == 0
        assert decision.files_changed == 0

    def test_binary_files_treated_as_zero(self) -> None:
        numstat = "-\t-\tbinary.png\n10\t5\tsrc/code.py"
        config = GrillTriggerConfig(max_lines=200, max_files=5)
        decision = should_grill(numstat, config=config)
        assert decision.lines_changed == 15
        assert decision.files_changed == 2


class TestGrillTranscript:
    """Tests for GrillTranscript model and render_markdown()."""

    def _make_transcript(self) -> GrillTranscript:
        return GrillTranscript(
            spec_id="SPEC-001",
            pr_ref="#42",
            questions=[
                GrillQA(
                    question="What edge cases exist?",
                    answer="Several boundary conditions need testing.",
                    confidence="high",
                ),
                GrillQA(
                    question="Any backwards-compatibility concerns?",
                    answer="The API surface is unchanged.",
                    confidence="medium",
                ),
                GrillQA(
                    question="What failure modes should be tested?",
                    answer="Network timeouts and malformed input.",
                    confidence="low",
                ),
            ],
            summary="All questions addressed with reasonable confidence.",
            generated_at=datetime(2026, 4, 12, 10, 0, 0),
        )

    def test_model_fields(self) -> None:
        t = self._make_transcript()
        assert t.spec_id == "SPEC-001"
        assert t.pr_ref == "#42"
        assert len(t.questions) == 3
        assert t.questions[0].confidence == "high"

    def test_render_markdown_contains_header(self) -> None:
        md = render_markdown(self._make_transcript())
        assert "# Grill-Yourself Transcript" in md

    def test_render_markdown_contains_spec_and_pr(self) -> None:
        md = render_markdown(self._make_transcript())
        assert "SPEC-001" in md
        assert "#42" in md

    def test_render_markdown_contains_questions(self) -> None:
        md = render_markdown(self._make_transcript())
        assert "Q1:" in md
        assert "Q2:" in md
        assert "Q3:" in md
        assert "What edge cases exist?" in md

    def test_render_markdown_contains_confidence_badges(self) -> None:
        md = render_markdown(self._make_transcript())
        assert "confidence-high" in md
        assert "confidence-medium" in md
        assert "confidence-low" in md

    def test_render_markdown_contains_summary(self) -> None:
        md = render_markdown(self._make_transcript())
        assert "## Summary" in md
        assert "All questions addressed" in md

    def test_render_markdown_no_spec_or_pr(self) -> None:
        t = GrillTranscript(
            questions=[
                GrillQA(question="Q?", answer="A.", confidence="high"),
            ],
            summary="Done.",
            generated_at=datetime(2026, 1, 1),
        )
        md = render_markdown(t)
        assert "**Spec:**" not in md
        assert "**PR:**" not in md
        assert "# Grill-Yourself Transcript" in md
