"""GrillTranscript model + markdown renderer (T066).

Per data-model.md section 9: stores the Q&A pairs from a grill-yourself session
and renders them as a markdown document for .specify/grills/.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from agent_power_pack.logging import get_logger

log = get_logger("grill.transcript")

CONFIDENCE_BADGE = {
    "high": "![high](https://img.shields.io/badge/confidence-high-green)",
    "medium": "![medium](https://img.shields.io/badge/confidence-medium-yellow)",
    "low": "![low](https://img.shields.io/badge/confidence-low-red)",
}


class GrillQA(BaseModel):
    """A single question-answer pair from a grill session."""

    question: str
    answer: str
    confidence: Literal["high", "medium", "low"]


class GrillTranscript(BaseModel):
    """Full transcript of a grill-yourself session."""

    spec_id: str | None = None
    pr_ref: str | None = None
    questions: list[GrillQA]
    summary: str
    generated_at: datetime = Field(default_factory=datetime.utcnow)


def render_markdown(transcript: GrillTranscript) -> str:
    """Render a GrillTranscript as a markdown document for .specify/grills/."""
    lines: list[str] = []

    lines.append("# Grill-Yourself Transcript")
    lines.append("")
    if transcript.spec_id:
        lines.append(f"**Spec:** {transcript.spec_id}")
    if transcript.pr_ref:
        lines.append(f"**PR:** {transcript.pr_ref}")
    lines.append(f"**Generated:** {transcript.generated_at.isoformat()}")
    lines.append("")
    lines.append("---")
    lines.append("")

    for i, qa in enumerate(transcript.questions, 1):
        badge = CONFIDENCE_BADGE.get(qa.confidence, "")
        lines.append(f"## Q{i}: {qa.question}")
        lines.append("")
        lines.append(f"**Confidence:** {badge}")
        lines.append("")
        lines.append(qa.answer)
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(transcript.summary)
    lines.append("")

    return "\n".join(lines)
