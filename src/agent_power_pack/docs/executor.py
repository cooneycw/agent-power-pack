"""DAG-based documentation generation pipeline (spec 002, FR-004/005/006/007/008/010).

Reads docs/plan.yaml, builds a dependency DAG, executes artifact generation in
topological order, routes each artifact to its assigned LLM via second-opinion
MCP, and publishes to Wiki.js.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from enum import Enum
from graphlib import CycleError, TopologicalSorter
from pathlib import Path
from typing import Any

import structlog
from ruamel.yaml import YAML

from agent_power_pack.docs.signal_detector import ROUTING_DEFAULTS

logger = structlog.get_logger()

# Maps plan.yaml model names to second-opinion MCP backend identifiers.
MODEL_TO_BACKEND: dict[str, str] = {
    "claude": "anthropic",
    "gpt-4o": "openai",
    "gemini": "gemini",
}

def resolve_model(artifact: dict[str, Any]) -> str:
    """Resolve the LLM model for an artifact (FR-005).

    Uses the explicit ``model`` field if set, otherwise falls back to
    ``ROUTING_DEFAULTS`` for the artifact type, then ``"claude"`` as the
    ultimate default for unknown/custom types.
    """
    explicit = artifact.get("model")
    if explicit:
        return str(explicit)
    art_type = artifact.get("type", "")
    return ROUTING_DEFAULTS.get(art_type, "claude")


def resolve_backend(model: str) -> str:
    """Map a model name to its second-opinion MCP backend identifier (FR-005).

    Unknown models are routed to ``"anthropic"`` (Claude) as the safe default.
    """
    return MODEL_TO_BACKEND.get(model, "anthropic")


# Artifact types that produce Mermaid diagram output (not Markdown prose).
MERMAID_TYPES: frozenset[str] = frozenset({"c4_diagrams", "sequence_diagrams"})

# The slides type uses the reportlab -> PDF -> PNG pipeline.
SLIDES_TYPE: str = "slides"


class ArtifactStatus(Enum):
    """Status of an artifact after pipeline execution (FR-009)."""

    success = "success"
    skipped = "skipped"
    retried = "retried"
    failed = "failed"
    pending = "pending"


@dataclass
class ArtifactFailure:
    """Diagnostic information for a failed artifact (FR-009).

    Provides the orchestrating agent with enough context to present
    a meaningful fix/skip/abort prompt to the developer.
    """

    artifact_type: str
    error: str
    error_type: str  # "missing_api_key", "code_execution", "validation", etc.
    suggested_fix: str
    artifact_config: dict[str, Any] = field(default_factory=dict)


@dataclass
class ArtifactResult:
    """Result of generating a single artifact."""

    artifact_type: str
    success: bool
    content: str = ""
    error: str = ""
    model: str = ""
    backend: str = ""
    wiki_page_id: int | None = None
    output_files: list[str] = field(default_factory=list)
    status: ArtifactStatus = ArtifactStatus.pending
    failure: ArtifactFailure | None = None


@dataclass
class PipelineResult:
    """Result of the full docs:auto pipeline run."""

    success: bool
    results: list[ArtifactResult] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    failures: list[ArtifactFailure] = field(default_factory=list)
    skipped_count: int = 0
    retried_count: int = 0


def load_plan(plan_path: Path) -> dict[str, Any]:
    """Load and validate docs/plan.yaml."""
    if not plan_path.exists():
        raise FileNotFoundError(f"Plan file not found: {plan_path}")

    yaml = YAML()
    with open(plan_path) as f:
        plan = yaml.load(f)

    if not plan or not isinstance(plan, dict):
        raise ValueError(f"Invalid plan file: {plan_path}")

    if "artifacts" not in plan:
        raise ValueError(f"Plan file missing 'artifacts' key: {plan_path}")

    return dict(plan)


def load_theme(theme_path: Path) -> dict[str, Any]:
    """Load docs/theme/theme.yaml, returning defaults if missing."""
    from agent_power_pack.docs.theme_analyzer import DEFAULT_THEME

    if not theme_path.exists():
        logger.warning("Theme file not found, using defaults", path=str(theme_path))
        return dict(DEFAULT_THEME)

    yaml = YAML()
    with open(theme_path) as f:
        theme = yaml.load(f)

    return dict(theme) if theme else dict(DEFAULT_THEME)


def build_dag(artifacts: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    """Build a dependency DAG and return artifacts in topological order, grouped by level.

    Each inner list contains artifacts that can execute in parallel (same
    topological level). Raises ValueError on cycles or missing dependencies.
    """
    type_to_artifact: dict[str, dict[str, Any]] = {}
    for art in artifacts:
        art_type = art.get("type", "")
        if not art_type:
            raise ValueError(f"Artifact missing 'type' field: {art}")
        type_to_artifact[art_type] = art

    # Validate dependencies exist
    for art in artifacts:
        for dep in art.get("depends_on", []):
            if dep not in type_to_artifact:
                raise ValueError(
                    f"Artifact '{art['type']}' depends on '{dep}' which is not in the plan. "
                    f"Available types: {sorted(type_to_artifact.keys())}"
                )

    # Build the topological sorter
    sorter: TopologicalSorter[str] = TopologicalSorter()
    for art in artifacts:
        deps = art.get("depends_on", [])
        sorter.add(art["type"], *deps)

    try:
        sorter.prepare()
    except CycleError as exc:
        raise ValueError(f"Circular dependency detected in plan: {exc}") from exc

    # Extract levels for potential parallel execution
    levels: list[list[dict[str, Any]]] = []
    while sorter.is_active():
        ready = sorted(sorter.get_ready())  # sort for determinism
        level = [type_to_artifact[t] for t in ready if t in type_to_artifact]
        if level:
            levels.append(level)
        for t in ready:
            sorter.done(t)

    return levels


def validate_wiki_path(
    wiki_path: str,
    convention: dict[str, Any] | None,
    project_name: str,
) -> bool:
    """Validate a wiki_path against the convention template (FR-008).

    Returns True if the path is valid or no convention exists.
    """
    if not convention or not wiki_path:
        return True

    paths = convention.get("paths", {})
    if not paths:
        return True

    # Build the set of valid path prefixes from the convention
    valid_prefixes = set()
    for segment_path in paths.values():
        resolved = segment_path.replace("{project}", project_name)
        valid_prefixes.add(resolved)

    # Check if wiki_path starts with any valid prefix
    for prefix in valid_prefixes:
        if wiki_path.startswith(prefix):
            return True

    return False


def get_current_sha(project_root: Path) -> str:
    """Get the current HEAD commit SHA."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=5,
            cwd=str(project_root),
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return ""


def build_generation_prompt(
    artifact: dict[str, Any],
    theme: dict[str, Any],
    project_root: Path,
) -> str:
    """Build the LLM prompt for generating a specific artifact.

    Returns a prompt string tailored to the artifact type, incorporating
    theme data and source signal context.
    """
    art_type = artifact.get("type", "")
    name = artifact.get("name", art_type)
    depth = artifact.get("depth", "overview")
    source_signals = artifact.get("source_signals", [])

    # Gather source context from signals
    source_context = _gather_source_context(source_signals, project_root)

    colors = theme.get("colors", {})
    fonts = theme.get("fonts", {})
    layouts = theme.get("layouts", {})

    if art_type == SLIDES_TYPE:
        return _build_slides_prompt(name, depth, source_context, colors, fonts, layouts)
    elif art_type in MERMAID_TYPES:
        return _build_mermaid_prompt(name, art_type, depth, source_context)
    else:
        # All other types produce Markdown (prose, API ref, ADRs, changelogs, custom)
        return _build_prose_prompt(name, art_type, depth, source_context)


def _gather_source_context(signals: list[str], project_root: Path) -> str:
    """Read source signal files/dirs to provide context to the LLM."""
    context_parts: list[str] = []
    max_chars = 8000  # Cap total context size

    for signal in signals:
        if signal.startswith("git "):
            # Git-based signals (tags, commits) — skip for now
            continue

        signal_path = project_root / signal
        if signal_path.is_file():
            try:
                content = signal_path.read_text(errors="replace")[:2000]
                context_parts.append(f"### {signal}\n```\n{content}\n```")
            except OSError:
                pass
        elif signal_path.is_dir():
            # List directory structure
            try:
                files = sorted(str(f.relative_to(project_root)) for f in signal_path.rglob("*") if f.is_file())[:20]
                context_parts.append(f"### {signal}\nFiles: {', '.join(files)}")
            except OSError:
                pass

        if sum(len(p) for p in context_parts) > max_chars:
            break

    return "\n\n".join(context_parts) if context_parts else "(no source context available)"


def _build_prose_prompt(name: str, art_type: str, depth: str, source_context: str) -> str:
    depth_guidance = {
        "overview": "Write a concise overview (500-1000 words).",
        "detailed": "Write a detailed document (1500-3000 words) with sections and examples.",
        "reference": "Write a comprehensive reference document with all public APIs, parameters, and return types.",
    }

    return f"""Generate a Markdown documentation artifact.

**Artifact**: {name}
**Type**: {art_type}
**Depth**: {depth}
**Guidance**: {depth_guidance.get(depth, depth_guidance['overview'])}

Use proper Markdown formatting with headers, code blocks, and lists as appropriate.
Do not include a title header — the Wiki.js page title will serve as the title.

## Source Context

{source_context}
"""


def _build_mermaid_prompt(name: str, art_type: str, depth: str, source_context: str) -> str:
    diagram_type = "C4Context" if art_type == "c4_diagrams" else "sequenceDiagram"
    return f"""Generate Mermaid diagrams for documentation.

**Artifact**: {name}
**Type**: {art_type} (use ```mermaid code blocks)
**Depth**: {depth}
**Preferred diagram type**: {diagram_type}

Output one or more Mermaid diagram code blocks embedded in Markdown. Add brief
explanatory text between diagrams. Do not include a title header.

## Source Context

{source_context}
"""


def _build_slides_prompt(
    name: str,
    depth: str,
    source_context: str,
    colors: dict[str, Any],
    fonts: dict[str, Any],
    layouts: dict[str, Any],
) -> str:
    width = layouts.get("slide_width", 1920)
    height = layouts.get("slide_height", 1080)

    return f"""Generate Python code using the `reportlab` library that creates a PDF slide deck.

**Artifact**: {name}
**Depth**: {depth}

## Requirements
- Canvas size: {width}x{height} points per page (landscape)
- Use `reportlab.lib.pagesizes` and `reportlab.pdfgen.canvas`
- Primary color: {colors.get('primary', '#2563EB')}
- Secondary color: {colors.get('secondary', '#64748B')}
- Accent color: {colors.get('accent', '#F59E0B')}
- Background: {colors.get('background', '#FFFFFF')}
- Text color: {colors.get('text', '#1E293B')}
- Heading font: {fonts.get('heading', 'Helvetica-Bold')}
- Body font: {fonts.get('body', 'Helvetica')}

## Output format
Output ONLY valid Python code (no markdown fences). The code must:
1. Import from reportlab
2. Accept an `output_path` variable (already defined) as the PDF output path
3. Create a Canvas with the specified page size
4. Draw 3-8 slides covering the key content
5. Call `canvas.save()` at the end

## Source Context

{source_context}
"""


def rasterize_pdf_to_pngs(pdf_path: Path, output_dir: Path, dpi: int = 150) -> list[Path]:
    """Rasterize a PDF to PNG images using PyMuPDF (FR-007, FR-020).

    Returns a list of PNG file paths, one per page.
    """
    try:
        import fitz  # type: ignore[import-untyped]  # PyMuPDF
    except ImportError:
        raise RuntimeError("PyMuPDF (fitz) is required for slide rasterization but not installed")

    output_dir.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(str(pdf_path))
    png_paths: list[Path] = []

    try:
        for page_num in range(doc.page_count):
            page = doc[page_num]
            # Scale factor for target DPI (default PDF is 72 DPI)
            scale = dpi / 72.0
            mat = fitz.Matrix(scale, scale)
            pix = page.get_pixmap(matrix=mat)

            png_path = output_dir / f"slide-{page_num + 1:03d}.png"
            pix.save(str(png_path))
            png_paths.append(png_path)
            logger.info("Rasterized slide", page=page_num + 1, path=str(png_path))
    finally:
        doc.close()

    return png_paths


def execute_slides_pipeline(
    reportlab_code: str,
    output_dir: Path,
) -> list[Path]:
    """Execute LLM-generated reportlab code to produce slides (FR-007).

    1. Execute the reportlab Python code to generate a PDF
    2. Rasterize the PDF to PNGs via PyMuPDF

    Returns a list of PNG file paths.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = output_dir / "slides.pdf"

    # Execute the reportlab code in a restricted namespace
    namespace: dict[str, Any] = {"output_path": str(pdf_path)}
    try:
        exec(reportlab_code, namespace)  # noqa: S102
    except Exception as exc:
        raise RuntimeError(f"Slides code execution failed: {exc}") from exc

    if not pdf_path.exists():
        raise RuntimeError(f"Slides code did not produce PDF at {pdf_path}")

    return rasterize_pdf_to_pngs(pdf_path, output_dir)


def update_plan_sha(
    plan_path: Path,
    artifact_type: str,
    sha: str,
    wiki_page_id: int | None = None,
) -> None:
    """Update last_commit_sha (and optionally wiki_page_id) for an artifact in plan.yaml (FR-010)."""
    yaml = YAML()
    yaml.default_flow_style = False

    with open(plan_path) as f:
        plan = yaml.load(f)

    for art in plan.get("artifacts", []):
        if art.get("type") == artifact_type:
            art["last_commit_sha"] = sha
            if wiki_page_id is not None:
                art["wiki_page_id"] = wiki_page_id
            break

    with open(plan_path, "w") as f:
        f.write("# Documentation plan — generated by docs:analyze (spec 002, FR-003).\n")
        f.write("# Edit freely; docs:auto respects your changes.\n")
        f.write("# Remove artifacts you don't want; add custom ones with type: custom.\n")
        f.write("\n")
        yaml.dump(plan, f)


def format_wiki_content(
    artifact: dict[str, Any],
    content: str,
    png_paths: list[Path] | None = None,
) -> str:
    """Format artifact content for Wiki.js publishing.

    For slides, creates an image gallery page. For all others, returns
    the content as-is (already Markdown).
    """
    if artifact.get("type") == SLIDES_TYPE and png_paths:
        # Build an image gallery page
        parts = [f"Slide deck with {len(png_paths)} slides.\n"]
        for i, png in enumerate(png_paths, 1):
            parts.append(f"## Slide {i}\n\n![Slide {i}]({png.name})\n")
        return "\n".join(parts)
    return content


def classify_error(
    error: Exception,
    artifact: dict[str, Any],
) -> ArtifactFailure:
    """Classify an artifact generation error and produce diagnostic info (FR-009).

    Returns an ArtifactFailure with error_type, human-readable error message,
    and a suggested fix the orchestrating agent can present to the developer.
    """
    art_type = artifact.get("type", "unknown")
    model = artifact.get("model", "claude")
    error_str = str(error)

    # Classify by error content
    if "api key" in error_str.lower() or "authentication" in error_str.lower():
        return ArtifactFailure(
            artifact_type=art_type,
            error=error_str,
            error_type="missing_api_key",
            suggested_fix=f"Provide the API key for '{model}', or use a different model (e.g., claude)",
            artifact_config=dict(artifact),
        )
    if isinstance(error, RuntimeError) and "execution failed" in error_str.lower():
        return ArtifactFailure(
            artifact_type=art_type,
            error=error_str,
            error_type="code_execution",
            suggested_fix="Review the generated reportlab code or adjust theme.yaml slide dimensions",
            artifact_config=dict(artifact),
        )
    if "wiki_path" in error_str.lower() or "convention" in error_str.lower():
        return ArtifactFailure(
            artifact_type=art_type,
            error=error_str,
            error_type="validation",
            suggested_fix="Fix the wiki_path in docs/plan.yaml to match the convention template",
            artifact_config=dict(artifact),
        )

    # Generic fallback
    return ArtifactFailure(
        artifact_type=art_type,
        error=error_str,
        error_type="unknown",
        suggested_fix="Investigate the error and retry, or skip this artifact",
        artifact_config=dict(artifact),
    )


def apply_artifact_override(
    artifact: dict[str, Any],
    overrides: dict[str, Any],
) -> dict[str, Any]:
    """Apply developer-provided overrides to an artifact config for retry (FR-009).

    Common overrides: model, depth, source_signals. Returns a new dict
    without modifying the original.
    """
    updated = dict(artifact)
    updated.update(overrides)
    return updated


def run_pipeline(
    plan_path: Path,
    project_root: Path,
    theme_path: Path | None = None,
    convention_path: Path | None = None,
    dry_run: bool = False,
) -> PipelineResult:
    """Execute the full docs:auto pipeline (FR-004).

    1. Load plan and theme
    2. Build dependency DAG
    3. Execute artifacts in topological order
    4. Update plan.yaml with commit SHAs

    Args:
        plan_path: Path to docs/plan.yaml
        project_root: Repository root
        theme_path: Path to docs/theme/theme.yaml (auto-detected if None)
        convention_path: Path to docs/wiki-structure.yaml (auto-detected if None)
        dry_run: If True, only validate the plan without generating

    Returns:
        PipelineResult with per-artifact results
    """
    # Load plan
    plan = load_plan(plan_path)
    project_name = plan.get("project", project_root.name)
    artifacts = plan.get("artifacts", [])

    if not artifacts:
        return PipelineResult(success=True, errors=["No artifacts in plan"])

    # Load theme
    if theme_path is None:
        theme_path = project_root / "docs" / "theme" / "theme.yaml"
    theme = load_theme(theme_path)

    # Load convention
    convention: dict[str, Any] | None = None
    if convention_path is None:
        convention_path = project_root / "docs" / "wiki-structure.yaml"
    if convention_path.exists():
        yaml = YAML()
        with open(convention_path) as f:
            convention = yaml.load(f)

    # Build DAG
    try:
        levels = build_dag(artifacts)
    except ValueError as exc:
        return PipelineResult(success=False, errors=[str(exc)])

    if dry_run:
        total = sum(len(level) for level in levels)
        return PipelineResult(
            success=True,
            errors=[f"Dry run: {total} artifacts in {len(levels)} levels"],
        )

    # Get current SHA for tracking
    current_sha = get_current_sha(project_root)

    # Execute artifacts level by level (FR-009: interactive failure recovery)
    pipeline_result = PipelineResult(success=True)

    for level_idx, level in enumerate(levels):
        logger.info("Executing DAG level", level=level_idx + 1, artifacts=[a["type"] for a in level])

        for artifact in level:
            art_type = artifact.get("type", "unknown")
            wiki_path = artifact.get("wiki_path")

            # Validate wiki path against convention (FR-008)
            if wiki_path and convention and not validate_wiki_path(wiki_path, convention, project_name):
                failure = ArtifactFailure(
                    artifact_type=art_type,
                    error=f"Wiki path '{wiki_path}' does not match convention template",
                    error_type="validation",
                    suggested_fix="Fix the wiki_path in docs/plan.yaml to match the convention template",
                    artifact_config=dict(artifact),
                )
                result = ArtifactResult(
                    artifact_type=art_type,
                    success=False,
                    error=failure.error,
                    status=ArtifactStatus.failed,
                    failure=failure,
                )
                pipeline_result.results.append(result)
                pipeline_result.failures.append(failure)
                pipeline_result.success = False
                logger.warning("Artifact failed validation", type=art_type, error=failure.error)
                # Continue to next artifact instead of stopping (FR-009)
                continue

            # Resolve LLM routing (FR-005)
            model = resolve_model(artifact)
            backend = resolve_backend(model)

            # Build the generation prompt
            try:
                prompt = build_generation_prompt(artifact, theme, project_root)
            except Exception as exc:
                failure = classify_error(exc, artifact)
                result = ArtifactResult(
                    artifact_type=art_type,
                    success=False,
                    error=str(exc),
                    status=ArtifactStatus.failed,
                    failure=failure,
                )
                pipeline_result.results.append(result)
                pipeline_result.failures.append(failure)
                pipeline_result.success = False
                logger.warning("Artifact prompt generation failed", type=art_type, error=str(exc))
                continue

            # Store the prompt for the orchestrating agent to execute
            result = ArtifactResult(
                artifact_type=art_type,
                success=True,
                content=prompt,
                model=model,
                backend=backend,
                status=ArtifactStatus.success,
            )

            # Handle slides pipeline specially
            if art_type == SLIDES_TYPE:
                result.output_files = []  # Will be populated by slide execution

            pipeline_result.results.append(result)

            # Update plan.yaml with SHA only for successful artifacts (FR-010)
            if current_sha:
                update_plan_sha(plan_path, art_type, current_sha)

            logger.info("Artifact prepared", type=art_type, model=model, backend=backend)

    return pipeline_result
