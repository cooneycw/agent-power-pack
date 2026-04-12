"""Pydantic models for the Woodpecker checklist validator (FR-017/018).

See data-model.md section 11 for the entity definitions.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class WoodpeckerRuleResult(BaseModel):
    """Result of evaluating a single checklist rule against a pipeline file."""

    rule_id: str
    status: Literal["pass", "fail", "waived"]
    evidence: str | None = None
    rationale: str


class WoodpeckerCheckResult(BaseModel):
    """Aggregate result of running the full Woodpecker checklist."""

    status: Literal["pass", "fail"]
    rules: list[WoodpeckerRuleResult]

    @property
    def failed_rules(self) -> list[WoodpeckerRuleResult]:
        return [r for r in self.rules if r.status == "fail"]

    @property
    def waived_rules(self) -> list[WoodpeckerRuleResult]:
        return [r for r in self.rules if r.status == "waived"]
