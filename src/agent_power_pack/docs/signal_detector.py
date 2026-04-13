"""Codebase signal detection for docs:analyze (spec 002, FR-003).

Scans the project for documentation signals and proposes artifacts with
type, confidence, source signals, and default LLM routing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger()

# Default LLM routing table (FR-015, from multi-model research 2026-04-12).
ROUTING_DEFAULTS: dict[str, str] = {
    "prose_docs": "claude",
    "api_reference": "gpt-4o",
    "c4_diagrams": "gemini",
    "sequence_diagrams": "gemini",
    "adrs": "claude",
    "slides": "gpt-4o",
    "changelogs": "gpt-4o",
}

# Artifact type display names and wiki path segments.
ARTIFACT_TYPE_META: dict[str, dict[str, str]] = {
    "prose_docs": {"name": "Project Guide", "wiki_segment": "guides"},
    "api_reference": {"name": "API Reference", "wiki_segment": "api"},
    "c4_diagrams": {"name": "C4 Architecture Diagrams", "wiki_segment": "diagrams"},
    "sequence_diagrams": {"name": "Sequence & Flow Diagrams", "wiki_segment": "diagrams"},
    "adrs": {"name": "Architecture Decision Records", "wiki_segment": "adrs"},
    "slides": {"name": "Project Overview Slides", "wiki_segment": "slides"},
    "changelogs": {"name": "Changelog", "wiki_segment": "changelog"},
}


@dataclass
class SignalMatch:
    """A detected documentation signal in the codebase."""

    artifact_type: str
    source_signals: list[str]
    confidence: float  # 0.0 to 1.0
    depth: str  # "overview", "detailed", "reference"


@dataclass
class ArtifactProposal:
    """A proposed documentation artifact for docs/plan.yaml."""

    name: str
    type: str
    model: str
    source_signals: list[str]
    depth: str
    confidence: float
    depends_on: list[str] = field(default_factory=list)
    wiki_path: str | None = None
    last_commit_sha: str | None = None


def detect_signals(project_root: Path) -> list[SignalMatch]:
    """Scan the project for documentation signals.

    Returns a list of SignalMatch objects, one per detected artifact type.
    """
    signals: list[SignalMatch] = []

    # --- Prose docs signals ---
    prose_sources: list[str] = []
    for name in ("README.md", "AGENTS.md", "CONTRIBUTING.md"):
        if (project_root / name).exists():
            prose_sources.append(name)
    if (project_root / "specs").is_dir():
        prose_sources.append("specs/")
    if (project_root / "compose.yaml").exists() or (project_root / "docker-compose.yaml").exists():
        prose_sources.append("compose.yaml")
    if (project_root / "Makefile").exists():
        prose_sources.append("Makefile")

    if prose_sources:
        signals.append(SignalMatch(
            artifact_type="prose_docs",
            source_signals=prose_sources,
            confidence=min(0.3 + 0.15 * len(prose_sources), 1.0),
            depth="detailed" if len(prose_sources) >= 3 else "overview",
        ))

    # --- API reference signals ---
    api_sources: list[str] = []
    src_dir = project_root / "src"
    if src_dir.is_dir():
        # Look for Python packages with public modules
        for pkg in src_dir.iterdir():
            if pkg.is_dir() and (pkg / "__init__.py").exists():
                py_files = list(pkg.rglob("*.py"))
                public_modules = [
                    f for f in py_files
                    if not f.name.startswith("_") or f.name == "__init__.py"
                ]
                if public_modules:
                    api_sources.append(f"src/{pkg.name}/")

    # Check for FastAPI/Flask routes
    for pattern in ("**/routes.py", "**/router.py", "**/api.py", "**/app.py"):
        route_files = list(project_root.glob(pattern))
        for rf in route_files:
            rel = str(rf.relative_to(project_root))
            if rel not in api_sources:
                api_sources.append(rel)

    # Check for MCP tool definitions
    mcp_dir = project_root / "mcp_container" / "servers"
    if mcp_dir.is_dir():
        for server_dir in mcp_dir.iterdir():
            if server_dir.is_dir():
                server_py = server_dir / "server.py"
                if server_py.exists():
                    api_sources.append(f"mcp_container/servers/{server_dir.name}/")

    if api_sources:
        signals.append(SignalMatch(
            artifact_type="api_reference",
            source_signals=api_sources,
            confidence=min(0.4 + 0.15 * len(api_sources), 1.0),
            depth="reference",
        ))

    # --- C4 diagrams signals ---
    c4_sources: list[str] = []
    for name in ("compose.yaml", "docker-compose.yaml", "docker-compose.yml"):
        if (project_root / name).exists():
            c4_sources.append(name)
    for name in ("Dockerfile", "Containerfile"):
        if (project_root / name).exists():
            c4_sources.append(name)
    # Service directories
    if mcp_dir.is_dir():
        c4_sources.append("mcp_container/servers/")
    # Look for Dockerfiles in subdirectories
    for df in project_root.rglob("Dockerfile"):
        rel = str(df.relative_to(project_root))
        if rel not in c4_sources and rel != "Dockerfile":
            c4_sources.append(rel)

    if c4_sources:
        signals.append(SignalMatch(
            artifact_type="c4_diagrams",
            source_signals=c4_sources,
            confidence=min(0.4 + 0.2 * len(c4_sources), 1.0),
            depth="detailed" if len(c4_sources) >= 3 else "overview",
        ))

    # --- Sequence/flow diagrams signals ---
    seq_sources: list[str] = []
    specs_dir = project_root / "specs"
    if specs_dir.is_dir():
        for spec in specs_dir.iterdir():
            if spec.is_dir():
                spec_md = spec / "spec.md"
                if spec_md.exists():
                    seq_sources.append(f"specs/{spec.name}/")
    # Look for pipeline/workflow code
    for pattern in ("**/pipeline*.py", "**/workflow*.py", "**/handler*.py"):
        for wf in project_root.glob(pattern):
            rel = str(wf.relative_to(project_root))
            if rel not in seq_sources:
                seq_sources.append(rel)
    # Manifests define multi-step workflows
    manifests_dir = project_root / "manifests"
    if manifests_dir.is_dir():
        manifest_families = [d.name for d in manifests_dir.iterdir() if d.is_dir()]
        if manifest_families:
            seq_sources.append("manifests/")

    if seq_sources:
        signals.append(SignalMatch(
            artifact_type="sequence_diagrams",
            source_signals=seq_sources,
            confidence=min(0.3 + 0.15 * len(seq_sources), 1.0),
            depth="detailed" if len(seq_sources) >= 3 else "overview",
        ))

    # --- ADR signals ---
    adr_sources: list[str] = []
    docs_dir = project_root / "docs"
    if docs_dir.is_dir():
        adrs_dir = docs_dir / "adrs"
        if adrs_dir.is_dir():
            adr_sources.append("docs/adrs/")
    # Specs contain architectural decisions
    if specs_dir.is_dir():
        adr_sources.append("specs/")
    # Git history with conventional commits (check for existing tags)
    if (project_root / ".git").exists() or (project_root / ".git").is_file():
        adr_sources.append("git history")

    if adr_sources:
        signals.append(SignalMatch(
            artifact_type="adrs",
            source_signals=adr_sources,
            confidence=min(0.2 + 0.2 * len(adr_sources), 0.8),
            depth="overview",
        ))

    # --- Slides signals ---
    slides_sources: list[str] = []
    if (project_root / "README.md").exists():
        slides_sources.append("README.md")
    if specs_dir.is_dir():
        slides_sources.append("specs/")
    # Changelog/milestones
    for name in ("CHANGELOG.md", "CHANGELOG"):
        if (project_root / name).exists():
            slides_sources.append(name)

    if slides_sources:
        signals.append(SignalMatch(
            artifact_type="slides",
            source_signals=slides_sources,
            confidence=min(0.2 + 0.1 * len(slides_sources), 0.6),
            depth="overview",
        ))

    # --- Changelog signals ---
    changelog_sources: list[str] = []
    for name in ("CHANGELOG.md", "CHANGELOG"):
        if (project_root / name).exists():
            changelog_sources.append(name)
    if (project_root / ".git").exists() or (project_root / ".git").is_file():
        changelog_sources.append("git tags/commits")
    if (project_root / "pyproject.toml").exists():
        changelog_sources.append("pyproject.toml (version)")

    if changelog_sources:
        signals.append(SignalMatch(
            artifact_type="changelogs",
            source_signals=changelog_sources,
            confidence=min(0.3 + 0.15 * len(changelog_sources), 0.8),
            depth="overview",
        ))

    return signals


def build_proposals(
    signals: list[SignalMatch],
    project_name: str,
    wiki_structure: dict[str, Any] | None = None,
) -> list[ArtifactProposal]:
    """Convert detected signals into artifact proposals.

    Each proposal includes the default LLM routing and optional Wiki.js path.
    """
    proposals: list[ArtifactProposal] = []

    for signal in signals:
        meta = ARTIFACT_TYPE_META.get(signal.artifact_type, {})
        name = meta.get("name", signal.artifact_type.replace("_", " ").title())
        wiki_segment = meta.get("wiki_segment", signal.artifact_type)

        wiki_path: str | None = None
        if wiki_structure:
            paths = wiki_structure.get("paths", {})
            wiki_path = paths.get(wiki_segment)
            if wiki_path:
                wiki_path = wiki_path.replace("{project}", project_name)

        # Set dependencies: slides depend on prose, sequence diagrams depend on C4
        depends_on: list[str] = []
        if signal.artifact_type == "slides":
            depends_on = ["prose_docs"]
        elif signal.artifact_type == "sequence_diagrams":
            depends_on = ["c4_diagrams"]

        proposals.append(ArtifactProposal(
            name=name,
            type=signal.artifact_type,
            model=ROUTING_DEFAULTS.get(signal.artifact_type, "claude"),
            source_signals=signal.source_signals,
            depth=signal.depth,
            confidence=round(signal.confidence, 2),
            depends_on=depends_on,
            wiki_path=wiki_path,
            last_commit_sha=None,
        ))

    return proposals
