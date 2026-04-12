"""Pydantic models for AGENTS.md lint results (T037).

Matches the contract at specs/001-foundation/contracts/agents-md-lint.result.schema.json.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel


class LintCheck(BaseModel):
    """A single lint check result."""

    rule_id: str
    status: Literal["pass", "fail", "warn"]
    message: str
    subject: Optional[str] = None


class LintResult(BaseModel):
    """Aggregate lint result for an AGENTS.md file."""

    status: Literal["pass", "fail"]
    checks: list[LintCheck]
    duration_ms: int
