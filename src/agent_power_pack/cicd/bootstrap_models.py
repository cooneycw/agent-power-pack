"""Pydantic models for the bootstrap dependency detector (issue #180).

Defines the config schema for `.specify/bootstrap-deps.yaml` and the
check result returned by the detector.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class BootstrapDependency(BaseModel):
    """A single admin-only bootstrap dependency."""

    id: str
    description: str
    paths: list[str] = Field(
        description="Glob patterns for files that, when changed, indicate this bootstrap dependency was modified.",
    )
    verify_command: str | None = Field(
        default=None,
        description="Shell command to verify the bootstrap has been applied (e.g., 'aws iam get-role --role-name X').",
    )
    manual_steps: list[str] = Field(
        default_factory=list,
        description="Human-readable instructions for the manual apply (e.g., 'terraform apply -target=aws_iam_role.xxx').",
    )


class BootstrapDepsConfig(BaseModel):
    """Schema for `.specify/bootstrap-deps.yaml`."""

    version: str = "1.0"
    dependencies: list[BootstrapDependency] = Field(default_factory=list)


class BootstrapMatch(BaseModel):
    """A single matched bootstrap dependency with the triggering files."""

    dependency_id: str
    description: str
    matched_files: list[str]
    manual_steps: list[str]
    verify_command: str | None = None


class BootstrapCheckResult(BaseModel):
    """Result of checking whether a diff touches bootstrap dependencies."""

    status: Literal["pass", "blocked"]
    matches: list[BootstrapMatch] = Field(default_factory=list)
    lock_sha: str | None = Field(
        default=None,
        description="Commit SHA recorded in .specify/bootstrap-applied.lock, if present.",
    )
    current_sha: str | None = Field(
        default=None,
        description="Current HEAD commit SHA.",
    )

    @property
    def blocking_message(self) -> str | None:
        """Human-readable blocking reminder, or None if status is pass."""
        if self.status == "pass":
            return None
        lines = [
            "BLOCKING REMINDER: This change touches admin-only bootstrap dependencies.",
            "Manual apply is required outside CI before deploying.",
            "",
        ]
        for match in self.matches:
            lines.append(f"  [{match.dependency_id}] {match.description}")
            for f in match.matched_files:
                lines.append(f"    Changed: {f}")
            for step in match.manual_steps:
                lines.append(f"    Required: {step}")
            if match.verify_command:
                lines.append(f"    Verify:   {match.verify_command}")
            lines.append("")
        lines.append(
            "After completing the manual steps, record the apply with:"
        )
        lines.append(
            '  echo "$(git rev-parse HEAD) $(date -Iseconds)" > .specify/bootstrap-applied.lock'
        )
        return "\n".join(lines)
