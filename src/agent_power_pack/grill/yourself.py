"""grill-yourself command implementation (T067).

Template-based pre-flight self-interrogation framework. For v0.1.0 this
generates intelligent template questions based on diff context and placeholder
answers (no LLM calls). The transcript is saved to .specify/grills/.
"""

from __future__ import annotations

import subprocess
from datetime import datetime
from pathlib import Path

from agent_power_pack.grill.transcript import GrillQA, GrillTranscript, render_markdown
from agent_power_pack.logging import get_logger

log = get_logger("grill.yourself")

# Categories of template questions keyed by heuristic
_GENERAL_QUESTIONS: list[str] = [
    "Are there any backwards-compatibility concerns with this change?",
    "How does this change affect the existing test suite?",
    "What failure modes should be tested?",
    "Does this change respect the project's architectural constraints?",
]

_LARGE_DIFF_QUESTIONS: list[str] = [
    "Is this change too large to review effectively and should it be split?",
    "Are there any performance implications from the size of this change?",
]

_MULTI_FILE_QUESTIONS: list[str] = [
    "Are cross-file dependencies handled correctly?",
    "Could any of these file changes be made independently?",
]


def _file_type_questions(filepaths: list[str]) -> list[str]:
    """Generate questions based on the types of files changed."""
    questions: list[str] = []
    extensions = {Path(fp).suffix for fp in filepaths}

    if ".py" in extensions:
        questions.append(
            f"What edge cases exist in the Python files changed ({', '.join(f for f in filepaths if f.endswith('.py'))})?"
        )
    if ".yaml" in extensions or ".yml" in extensions:
        questions.append(
            "Have the YAML schema changes been validated against existing consumers?"
        )
    if any(fp.startswith("tests/") for fp in filepaths):
        questions.append(
            "Do the test changes adequately cover the new/modified production code?"
        )
    if any("__init__" in fp for fp in filepaths):
        questions.append(
            "Do the __init__.py export changes maintain a clean public API surface?"
        )
    return questions


def _collect_diff_context() -> tuple[str, list[str]]:
    """Collect git diff context for question generation.

    Returns:
        Tuple of (numstat output, list of changed filepaths).
    """
    try:
        result = subprocess.run(
            ["git", "diff", "--numstat", "HEAD~1"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        numstat = result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        numstat = ""

    filepaths: list[str] = []
    for line in numstat.splitlines():
        parts = line.strip().split("\t", 2)
        if len(parts) >= 3:
            filepaths.append(parts[2])

    return numstat, filepaths


def generate_questions(
    filepaths: list[str],
    total_lines: int = 0,
) -> list[GrillQA]:
    """Generate template-based grill questions from diff context.

    Args:
        filepaths: List of changed file paths.
        total_lines: Total lines changed (added + deleted).

    Returns:
        List of GrillQA with template answers.
    """
    questions: list[str] = list(_GENERAL_QUESTIONS)

    if total_lines > 100:
        questions.extend(_LARGE_DIFF_QUESTIONS)

    if len(filepaths) > 3:
        questions.extend(_MULTI_FILE_QUESTIONS)

    questions.extend(_file_type_questions(filepaths))

    # Ensure at least 5 questions
    while len(questions) < 5:
        questions.append(
            "What assumptions does this change make that should be documented?"
        )

    qa_list: list[GrillQA] = []
    for q in questions:
        qa_list.append(
            GrillQA(
                question=q,
                answer=(
                    "[Template] This answer should be filled in by an LLM or human reviewer. "
                    "Analyze the diff context and provide a substantive response."
                ),
                confidence="low",
            )
        )

    return qa_list


def run_grill_yourself(
    plan: str | None = None,
    spec_id: str | None = None,
    pr_ref: str | None = None,
) -> GrillTranscript:
    """Run the grill-yourself pre-flight self-interrogation.

    For v0.1.0, generates template-based questions from diff context.
    Saves the transcript to .specify/grills/.

    Args:
        plan: Optional plan text to incorporate into questions.
        spec_id: Spec ID for transcript filename.
        pr_ref: PR reference to attach to the transcript.

    Returns:
        The generated GrillTranscript.
    """
    log.info("running grill-yourself", spec_id=spec_id, pr_ref=pr_ref)

    numstat, filepaths = _collect_diff_context()

    # Compute total lines
    total_lines = 0
    for line in numstat.splitlines():
        parts = line.strip().split("\t", 2)
        if len(parts) >= 3:
            added = int(parts[0]) if parts[0] != "-" else 0
            deleted = int(parts[1]) if parts[1] != "-" else 0
            total_lines += added + deleted

    questions = generate_questions(filepaths, total_lines)

    summary_parts = [
        f"Grill-yourself generated {len(questions)} template questions "
        f"for {len(filepaths)} changed files ({total_lines} lines changed).",
    ]
    if plan:
        summary_parts.append(f"Plan context: {plan}")
    summary_parts.append(
        "All answers are placeholders — run with an LLM backend for substantive responses."
    )

    transcript = GrillTranscript(
        spec_id=spec_id,
        pr_ref=pr_ref,
        questions=questions,
        summary=" ".join(summary_parts),
        generated_at=datetime.utcnow(),
    )

    # Save to .specify/grills/
    grills_dir = Path(".specify/grills")
    grills_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{spec_id}.md" if spec_id else f"grill-{transcript.generated_at.strftime('%Y%m%dT%H%M%S')}.md"
    output_path = grills_dir / filename
    output_path.write_text(render_markdown(transcript), encoding="utf-8")

    log.info("grill transcript saved", path=str(output_path))
    return transcript
