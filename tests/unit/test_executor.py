"""Unit tests for docs/executor.py (spec 002, FR-004/005/006/007/008/010)."""

from __future__ import annotations

from pathlib import Path

import pytest
from ruamel.yaml import YAML

from agent_power_pack.docs.executor import (
    build_dag,
    build_generation_prompt,
    execute_slides_pipeline,
    load_plan,
    load_theme,
    run_pipeline,
    update_plan_sha,
    validate_wiki_path,
)


def _write_plan(path: Path, artifacts: list[dict], project: str = "test") -> None:
    yaml = YAML()
    with open(path, "w") as f:
        yaml.dump({
            "project": project,
            "convention": "docs/wiki-structure.yaml",
            "artifacts": artifacts,
        }, f)


def _write_convention(path: Path, project: str = "test") -> None:
    yaml = YAML()
    with open(path, "w") as f:
        yaml.dump({
            "project": project,
            "paths": {
                "guides": f"{project}/guides",
                "api": f"{project}/api",
                "diagrams": f"{project}/diagrams",
                "adrs": f"{project}/adrs",
                "slides": f"{project}/slides",
                "changelog": f"{project}/changelog",
            },
        }, f)


# --- load_plan ---

@pytest.mark.unit
class TestLoadPlan:
    def test_loads_valid_plan(self, tmp_path: Path) -> None:
        plan_path = tmp_path / "plan.yaml"
        _write_plan(plan_path, [{"type": "prose_docs", "name": "Guide"}])
        plan = load_plan(plan_path)
        assert plan["project"] == "test"
        assert len(plan["artifacts"]) == 1

    def test_raises_on_missing_file(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            load_plan(tmp_path / "nonexistent.yaml")

    def test_raises_on_empty_file(self, tmp_path: Path) -> None:
        plan_path = tmp_path / "plan.yaml"
        plan_path.write_text("")
        with pytest.raises(ValueError, match="Invalid plan"):
            load_plan(plan_path)

    def test_raises_on_missing_artifacts(self, tmp_path: Path) -> None:
        plan_path = tmp_path / "plan.yaml"
        yaml = YAML()
        with open(plan_path, "w") as f:
            yaml.dump({"project": "test"}, f)
        with pytest.raises(ValueError, match="missing 'artifacts'"):
            load_plan(plan_path)


# --- build_dag ---

@pytest.mark.unit
class TestBuildDag:
    def test_single_artifact_no_deps(self) -> None:
        artifacts = [{"type": "prose_docs", "name": "Guide"}]
        levels = build_dag(artifacts)
        assert len(levels) == 1
        assert levels[0][0]["type"] == "prose_docs"

    def test_dependency_ordering(self) -> None:
        """AC: A generates before B when B depends_on A."""
        artifacts = [
            {"type": "slides", "name": "Slides", "depends_on": ["prose_docs"]},
            {"type": "prose_docs", "name": "Guide"},
        ]
        levels = build_dag(artifacts)
        assert len(levels) == 2
        assert levels[0][0]["type"] == "prose_docs"
        assert levels[1][0]["type"] == "slides"

    def test_independent_artifacts_same_level(self) -> None:
        """AC: Independent artifacts can run in parallel (same level)."""
        artifacts = [
            {"type": "prose_docs", "name": "Guide"},
            {"type": "api_reference", "name": "API"},
            {"type": "adrs", "name": "ADRs"},
        ]
        levels = build_dag(artifacts)
        assert len(levels) == 1
        assert len(levels[0]) == 3

    def test_multi_level_dag(self) -> None:
        artifacts = [
            {"type": "prose_docs", "name": "Guide"},
            {"type": "c4_diagrams", "name": "C4"},
            {"type": "slides", "name": "Slides", "depends_on": ["prose_docs"]},
            {"type": "sequence_diagrams", "name": "Seq", "depends_on": ["c4_diagrams"]},
        ]
        levels = build_dag(artifacts)
        assert len(levels) == 2
        level0_types = sorted(a["type"] for a in levels[0])
        level1_types = sorted(a["type"] for a in levels[1])
        assert "prose_docs" in level0_types
        assert "c4_diagrams" in level0_types
        assert "slides" in level1_types
        assert "sequence_diagrams" in level1_types

    def test_cycle_detection(self) -> None:
        """Edge case: circular depends_on detected."""
        artifacts = [
            {"type": "a", "name": "A", "depends_on": ["b"]},
            {"type": "b", "name": "B", "depends_on": ["a"]},
        ]
        with pytest.raises(ValueError, match="Circular dependency"):
            build_dag(artifacts)

    def test_missing_dependency(self) -> None:
        artifacts = [
            {"type": "slides", "name": "Slides", "depends_on": ["prose_docs"]},
        ]
        with pytest.raises(ValueError, match="depends on 'prose_docs' which is not in the plan"):
            build_dag(artifacts)

    def test_missing_type_field(self) -> None:
        artifacts = [{"name": "Bad"}]
        with pytest.raises(ValueError, match="missing 'type'"):
            build_dag(artifacts)

    def test_deterministic_ordering(self) -> None:
        """Same input always produces same output (sorted within levels)."""
        artifacts = [
            {"type": "changelogs", "name": "Changelog"},
            {"type": "adrs", "name": "ADRs"},
            {"type": "prose_docs", "name": "Guide"},
        ]
        levels1 = build_dag(artifacts)
        levels2 = build_dag(list(reversed(artifacts)))
        types1 = [a["type"] for a in levels1[0]]
        types2 = [a["type"] for a in levels2[0]]
        assert types1 == types2


# --- validate_wiki_path ---

@pytest.mark.unit
class TestValidateWikiPath:
    def test_valid_path(self) -> None:
        convention = {"paths": {"guides": "myproject/guides"}}
        assert validate_wiki_path("myproject/guides/intro", convention, "myproject")

    def test_invalid_path(self) -> None:
        convention = {"paths": {"guides": "myproject/guides"}}
        assert not validate_wiki_path("other/random/path", convention, "myproject")

    def test_no_convention(self) -> None:
        assert validate_wiki_path("anything/goes", None, "test")

    def test_empty_wiki_path(self) -> None:
        convention = {"paths": {"guides": "test/guides"}}
        assert validate_wiki_path("", convention, "test")

    def test_project_substitution(self) -> None:
        convention = {"paths": {"guides": "{project}/guides"}}
        assert validate_wiki_path("myproject/guides/page", convention, "myproject")


# --- update_plan_sha ---

@pytest.mark.unit
class TestUpdatePlanSha:
    def test_updates_sha(self, tmp_path: Path) -> None:
        """AC: last_commit_sha updated per artifact on success."""
        plan_path = tmp_path / "plan.yaml"
        _write_plan(plan_path, [
            {"type": "prose_docs", "name": "Guide", "last_commit_sha": None},
        ])
        update_plan_sha(plan_path, "prose_docs", "abc123")

        yaml = YAML()
        with open(plan_path) as f:
            plan = yaml.load(f)
        assert plan["artifacts"][0]["last_commit_sha"] == "abc123"

    def test_updates_wiki_page_id(self, tmp_path: Path) -> None:
        plan_path = tmp_path / "plan.yaml"
        _write_plan(plan_path, [
            {"type": "prose_docs", "name": "Guide", "last_commit_sha": None},
        ])
        update_plan_sha(plan_path, "prose_docs", "abc123", wiki_page_id=42)

        yaml = YAML()
        with open(plan_path) as f:
            plan = yaml.load(f)
        assert plan["artifacts"][0]["wiki_page_id"] == 42

    def test_no_match_is_noop(self, tmp_path: Path) -> None:
        plan_path = tmp_path / "plan.yaml"
        _write_plan(plan_path, [
            {"type": "prose_docs", "name": "Guide", "last_commit_sha": None},
        ])
        update_plan_sha(plan_path, "nonexistent_type", "abc123")

        yaml = YAML()
        with open(plan_path) as f:
            plan = yaml.load(f)
        assert plan["artifacts"][0]["last_commit_sha"] is None


# --- build_generation_prompt ---

@pytest.mark.unit
class TestBuildGenerationPrompt:
    def test_prose_prompt(self, tmp_path: Path) -> None:
        artifact = {"type": "prose_docs", "name": "Guide", "depth": "detailed", "source_signals": []}
        theme = {"colors": {}, "fonts": {}, "layouts": {}}
        prompt = build_generation_prompt(artifact, theme, tmp_path)
        assert "Markdown" in prompt
        assert "detailed" in prompt

    def test_slides_prompt(self, tmp_path: Path) -> None:
        artifact = {"type": "slides", "name": "Deck", "depth": "overview", "source_signals": []}
        theme = {
            "colors": {"primary": "#FF0000"},
            "fonts": {"heading": "Arial"},
            "layouts": {"slide_width": 1920, "slide_height": 1080},
        }
        prompt = build_generation_prompt(artifact, theme, tmp_path)
        assert "reportlab" in prompt
        assert "1920" in prompt
        assert "#FF0000" in prompt

    def test_mermaid_prompt(self, tmp_path: Path) -> None:
        artifact = {"type": "c4_diagrams", "name": "C4", "depth": "overview", "source_signals": []}
        theme = {"colors": {}, "fonts": {}, "layouts": {}}
        prompt = build_generation_prompt(artifact, theme, tmp_path)
        assert "Mermaid" in prompt
        assert "C4Context" in prompt

    def test_sequence_diagram_prompt(self, tmp_path: Path) -> None:
        artifact = {"type": "sequence_diagrams", "name": "Seq", "depth": "overview", "source_signals": []}
        theme = {"colors": {}, "fonts": {}, "layouts": {}}
        prompt = build_generation_prompt(artifact, theme, tmp_path)
        assert "sequenceDiagram" in prompt

    def test_custom_type_uses_prose(self, tmp_path: Path) -> None:
        """AC: Custom artifact types treated as prose-default."""
        artifact = {"type": "custom_runbook", "name": "Runbook", "depth": "overview", "source_signals": []}
        theme = {"colors": {}, "fonts": {}, "layouts": {}}
        prompt = build_generation_prompt(artifact, theme, tmp_path)
        assert "Markdown" in prompt

    def test_source_context_included(self, tmp_path: Path) -> None:
        (tmp_path / "README.md").write_text("# Hello World")
        artifact = {"type": "prose_docs", "name": "Guide", "depth": "overview", "source_signals": ["README.md"]}
        theme = {"colors": {}, "fonts": {}, "layouts": {}}
        prompt = build_generation_prompt(artifact, theme, tmp_path)
        assert "Hello World" in prompt


# --- load_theme ---

@pytest.mark.unit
class TestLoadTheme:
    def test_loads_theme(self, tmp_path: Path) -> None:
        theme_path = tmp_path / "theme.yaml"
        yaml = YAML()
        with open(theme_path, "w") as f:
            yaml.dump({"colors": {"primary": "#FF0000"}, "fonts": {"heading": "Arial"}}, f)
        theme = load_theme(theme_path)
        assert theme["colors"]["primary"] == "#FF0000"

    def test_returns_defaults_on_missing(self, tmp_path: Path) -> None:
        theme = load_theme(tmp_path / "missing.yaml")
        assert "colors" in theme
        assert "fonts" in theme


# --- run_pipeline ---

@pytest.mark.unit
class TestRunPipeline:
    def test_dry_run(self, tmp_path: Path) -> None:
        plan_path = tmp_path / "docs" / "plan.yaml"
        plan_path.parent.mkdir(parents=True)
        _write_plan(plan_path, [
            {"type": "prose_docs", "name": "Guide"},
            {"type": "slides", "name": "Slides", "depends_on": ["prose_docs"]},
        ])
        result = run_pipeline(plan_path, tmp_path, dry_run=True)
        assert result.success
        assert "Dry run" in result.errors[0]

    def test_empty_plan(self, tmp_path: Path) -> None:
        plan_path = tmp_path / "docs" / "plan.yaml"
        plan_path.parent.mkdir(parents=True)
        _write_plan(plan_path, [])
        result = run_pipeline(plan_path, tmp_path)
        assert result.success
        assert "No artifacts" in result.errors[0]

    def test_cycle_returns_error(self, tmp_path: Path) -> None:
        plan_path = tmp_path / "docs" / "plan.yaml"
        plan_path.parent.mkdir(parents=True)
        _write_plan(plan_path, [
            {"type": "a", "name": "A", "depends_on": ["b"]},
            {"type": "b", "name": "B", "depends_on": ["a"]},
        ])
        result = run_pipeline(plan_path, tmp_path)
        assert not result.success
        assert any("Circular" in e for e in result.errors)

    def test_convention_violation_stops_pipeline(self, tmp_path: Path) -> None:
        """AC: Page paths follow convention template."""
        plan_path = tmp_path / "docs" / "plan.yaml"
        plan_path.parent.mkdir(parents=True)
        _write_plan(plan_path, [
            {"type": "prose_docs", "name": "Guide", "wiki_path": "bad/invalid/path"},
        ])
        conv_path = tmp_path / "docs" / "wiki-structure.yaml"
        _write_convention(conv_path)
        result = run_pipeline(plan_path, tmp_path, convention_path=conv_path)
        assert not result.success

    def test_successful_pipeline_updates_sha(self, tmp_path: Path) -> None:
        """AC: last_commit_sha updated per artifact."""
        plan_path = tmp_path / "docs" / "plan.yaml"
        plan_path.parent.mkdir(parents=True)
        _write_plan(plan_path, [
            {"type": "prose_docs", "name": "Guide", "last_commit_sha": None},
        ])
        # Initialize a git repo for SHA detection
        import subprocess
        env = {"GIT_AUTHOR_NAME": "Test", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "Test", "GIT_COMMITTER_EMAIL": "t@t", "HOME": str(tmp_path)}
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True, env={**env, "PATH": "/usr/bin:/bin"})
        subprocess.run(["git", "commit", "--allow-empty", "-m", "init"], cwd=tmp_path, capture_output=True, env={**env, "PATH": "/usr/bin:/bin"})

        result = run_pipeline(plan_path, tmp_path)
        assert result.success

        yaml = YAML()
        with open(plan_path) as f:
            plan = yaml.load(f)
        assert plan["artifacts"][0]["last_commit_sha"] is not None


# --- execute_slides_pipeline ---

@pytest.mark.unit
class TestExecuteSlidesPipeline:
    def test_valid_reportlab_code(self, tmp_path: Path) -> None:
        """AC: Slides pipeline: reportlab code -> PDF -> PNG."""
        code = """
from reportlab.pdfgen.canvas import Canvas
from reportlab.lib.pagesizes import landscape
c = Canvas(output_path, pagesize=(1920, 1080))
c.setFont("Helvetica", 48)
c.drawString(100, 540, "Test Slide")
c.showPage()
c.save()
"""
        pngs = execute_slides_pipeline(code, tmp_path)
        assert len(pngs) == 1
        assert pngs[0].exists()
        assert pngs[0].suffix == ".png"

    def test_bad_code_raises(self, tmp_path: Path) -> None:
        with pytest.raises(RuntimeError, match="execution failed"):
            execute_slides_pipeline("raise ValueError('bad')", tmp_path)

    def test_no_pdf_output_raises(self, tmp_path: Path) -> None:
        with pytest.raises(RuntimeError, match="did not produce PDF"):
            execute_slides_pipeline("x = 1", tmp_path)
