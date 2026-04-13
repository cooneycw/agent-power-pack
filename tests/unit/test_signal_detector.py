"""Unit tests for docs/signal_detector.py (spec 002, FR-003)."""

from __future__ import annotations

from pathlib import Path

import pytest

from agent_power_pack.docs.signal_detector import (
    ROUTING_DEFAULTS,
    build_proposals,
    detect_signals,
)


@pytest.mark.unit
class TestDetectSignals:
    def test_empty_project(self, tmp_path: Path) -> None:
        signals = detect_signals(tmp_path)
        assert signals == []

    def test_detects_prose_from_readme(self, tmp_path: Path) -> None:
        (tmp_path / "README.md").write_text("# Hello")
        signals = detect_signals(tmp_path)
        prose = [s for s in signals if s.artifact_type == "prose_docs"]
        assert len(prose) == 1
        assert "README.md" in prose[0].source_signals

    def test_detects_api_reference(self, tmp_path: Path) -> None:
        pkg = tmp_path / "src" / "mylib"
        pkg.mkdir(parents=True)
        (pkg / "__init__.py").write_text("")
        (pkg / "core.py").write_text("def hello(): pass")
        signals = detect_signals(tmp_path)
        api = [s for s in signals if s.artifact_type == "api_reference"]
        assert len(api) == 1
        assert "src/mylib/" in api[0].source_signals

    def test_detects_c4_from_compose(self, tmp_path: Path) -> None:
        (tmp_path / "compose.yaml").write_text("services: {}")
        signals = detect_signals(tmp_path)
        c4 = [s for s in signals if s.artifact_type == "c4_diagrams"]
        assert len(c4) == 1
        assert "compose.yaml" in c4[0].source_signals

    def test_detects_c4_from_dockerfile(self, tmp_path: Path) -> None:
        (tmp_path / "Dockerfile").write_text("FROM python:3.11")
        signals = detect_signals(tmp_path)
        c4 = [s for s in signals if s.artifact_type == "c4_diagrams"]
        assert len(c4) == 1

    def test_detects_changelogs(self, tmp_path: Path) -> None:
        (tmp_path / "CHANGELOG.md").write_text("# Changelog")
        (tmp_path / "pyproject.toml").write_text('[project]\nversion = "1.0"')
        # Create .git so git signals fire
        (tmp_path / ".git").mkdir()
        signals = detect_signals(tmp_path)
        cl = [s for s in signals if s.artifact_type == "changelogs"]
        assert len(cl) == 1
        assert cl[0].confidence > 0.3

    def test_detects_adrs(self, tmp_path: Path) -> None:
        (tmp_path / "docs" / "adrs").mkdir(parents=True)
        (tmp_path / ".git").mkdir()
        signals = detect_signals(tmp_path)
        adrs = [s for s in signals if s.artifact_type == "adrs"]
        assert len(adrs) == 1
        assert "docs/adrs/" in adrs[0].source_signals

    def test_detects_sequence_from_specs(self, tmp_path: Path) -> None:
        spec_dir = tmp_path / "specs" / "001-foundation"
        spec_dir.mkdir(parents=True)
        (spec_dir / "spec.md").write_text("# Spec")
        signals = detect_signals(tmp_path)
        seq = [s for s in signals if s.artifact_type == "sequence_diagrams"]
        assert len(seq) == 1

    def test_detects_mcp_tools_as_api_signals(self, tmp_path: Path) -> None:
        server_dir = tmp_path / "mcp_container" / "servers" / "wikijs"
        server_dir.mkdir(parents=True)
        (server_dir / "server.py").write_text("@mcp.tool()")
        signals = detect_signals(tmp_path)
        api = [s for s in signals if s.artifact_type == "api_reference"]
        assert len(api) == 1
        assert any("mcp_container" in s for s in api[0].source_signals)

    def test_confidence_increases_with_signals(self, tmp_path: Path) -> None:
        (tmp_path / "README.md").write_text("# Hello")
        signals_few = detect_signals(tmp_path)

        (tmp_path / "AGENTS.md").write_text("# Agents")
        (tmp_path / "Makefile").write_text("all:")
        (tmp_path / "compose.yaml").write_text("services: {}")
        (tmp_path / "specs").mkdir()
        signals_many = detect_signals(tmp_path)

        prose_few = [s for s in signals_few if s.artifact_type == "prose_docs"][0]
        prose_many = [s for s in signals_many if s.artifact_type == "prose_docs"][0]
        assert prose_many.confidence > prose_few.confidence

    def test_full_project_detects_minimum_c4_and_api(self, tmp_path: Path) -> None:
        """AC: Plan proposes at minimum C4 + API ref for Python project with compose.yaml."""
        (tmp_path / "compose.yaml").write_text("services: {}")
        pkg = tmp_path / "src" / "mylib"
        pkg.mkdir(parents=True)
        (pkg / "__init__.py").write_text("")
        (pkg / "api.py").write_text("def endpoint(): pass")

        signals = detect_signals(tmp_path)
        types = {s.artifact_type for s in signals}
        assert "c4_diagrams" in types
        assert "api_reference" in types


@pytest.mark.unit
class TestBuildProposals:
    def test_proposals_have_routing_defaults(self, tmp_path: Path) -> None:
        (tmp_path / "README.md").write_text("# Hi")
        (tmp_path / "compose.yaml").write_text("services: {}")
        signals = detect_signals(tmp_path)
        proposals = build_proposals(signals, "test-project")
        for p in proposals:
            assert p.model == ROUTING_DEFAULTS[p.type]

    def test_wiki_paths_resolved(self, tmp_path: Path) -> None:
        (tmp_path / "README.md").write_text("# Hi")
        signals = detect_signals(tmp_path)
        wiki_structure = {
            "paths": {
                "guides": "{project}/guides",
                "api": "{project}/api",
            },
        }
        proposals = build_proposals(signals, "myproject", wiki_structure)
        prose = [p for p in proposals if p.type == "prose_docs"]
        if prose:
            assert prose[0].wiki_path == "myproject/guides"

    def test_slides_depend_on_prose(self, tmp_path: Path) -> None:
        (tmp_path / "README.md").write_text("# Hi")
        (tmp_path / "specs").mkdir()
        signals = detect_signals(tmp_path)
        proposals = build_proposals(signals, "test")
        slides = [p for p in proposals if p.type == "slides"]
        if slides:
            assert "prose_docs" in slides[0].depends_on

    def test_empty_signals_empty_proposals(self) -> None:
        proposals = build_proposals([], "test")
        assert proposals == []
