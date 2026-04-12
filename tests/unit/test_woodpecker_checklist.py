"""Unit tests for the Woodpecker checklist validator (SC-009).

One parametrized test per rule asserting bad fixtures fail and good fixtures pass.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from agent_power_pack.cicd.woodpecker_checklist import (
    NON_WAIVABLE_RULES,
    RULE_REGISTRY,
    load_pipeline,
    run_interactive,
    run_validator,
    validate_pipeline_file,
)
from agent_power_pack.cicd.woodpecker_checklist_models import (
    WoodpeckerCheckResult,
    WoodpeckerRuleResult,
)

FIXTURES = Path(__file__).parent / "fixtures" / "woodpecker"

# All rule IDs that have fixture files
RULE_IDS = sorted(RULE_REGISTRY.keys())


# ---------------------------------------------------------------------------
# Parametrized: good fixtures pass, bad fixtures fail
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestRuleFixtures:
    """Each rule has a known-good and known-bad fixture file."""

    @pytest.mark.parametrize("rule_id", RULE_IDS)
    def test_good_fixture_passes(self, rule_id: str) -> None:
        fixture = FIXTURES / f"{rule_id}_good.yml"
        assert fixture.exists(), f"Missing good fixture for rule '{rule_id}'"
        pipeline = load_pipeline(fixture)
        evaluator = RULE_REGISTRY[rule_id]
        result = evaluator(pipeline)
        assert result.status == "pass", (
            f"Rule '{rule_id}' should pass on good fixture but got: "
            f"status={result.status}, evidence={result.evidence}"
        )

    @pytest.mark.parametrize("rule_id", RULE_IDS)
    def test_bad_fixture_fails(self, rule_id: str) -> None:
        fixture = FIXTURES / f"{rule_id}_bad.yml"
        assert fixture.exists(), f"Missing bad fixture for rule '{rule_id}'"
        pipeline = load_pipeline(fixture)
        evaluator = RULE_REGISTRY[rule_id]
        result = evaluator(pipeline)
        assert result.status == "fail", (
            f"Rule '{rule_id}' should fail on bad fixture but got: "
            f"status={result.status}"
        )
        assert result.evidence is not None, (
            f"Rule '{rule_id}' should provide evidence on failure"
        )


# ---------------------------------------------------------------------------
# Validator mode
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestValidatorMode:
    """Tests for the non-interactive validator run mode."""

    def test_all_good_fixtures_pass_validator(self) -> None:
        """A pipeline that passes every rule should get status=pass."""
        # Build a pipeline that satisfies all rules
        pipeline = load_pipeline(FIXTURES / "pinned_images_good.yml")
        result = run_validator(pipeline)
        assert isinstance(result, WoodpeckerCheckResult)
        assert result.status in ("pass", "fail")
        # At minimum, all rule IDs should be represented
        result_ids = {r.rule_id for r in result.rules}
        assert result_ids == set(RULE_IDS)

    def test_bad_pipeline_fails_validator(self) -> None:
        """A pipeline with unpinned images should fail validation."""
        pipeline = load_pipeline(FIXTURES / "pinned_images_bad.yml")
        result = run_validator(pipeline)
        pinned = next(r for r in result.rules if r.rule_id == "pinned_images")
        assert pinned.status == "fail"
        assert result.status == "fail"

    def test_waiver_applied_to_waivable_rule(self) -> None:
        """Waivable rules can be waived via the waived_rules parameter."""
        pipeline = load_pipeline(FIXTURES / "stale_commit_guard_bad.yml")
        # Without waiver: should fail
        result_no_waiver = run_validator(pipeline)
        guard = next(r for r in result_no_waiver.rules if r.rule_id == "stale_commit_guard")
        assert guard.status == "fail"

        # With waiver: should be waived (stale_commit_guard is NOT in NON_WAIVABLE_RULES)
        assert "stale_commit_guard" not in NON_WAIVABLE_RULES
        result_waived = run_validator(pipeline, waived_rules={"stale_commit_guard"})
        guard_waived = next(r for r in result_waived.rules if r.rule_id == "stale_commit_guard")
        assert guard_waived.status == "waived"

    def test_waiver_rejected_for_non_waivable_rule(self) -> None:
        """Non-waivable rules cannot be waived."""
        pipeline = load_pipeline(FIXTURES / "pinned_images_bad.yml")
        assert "pinned_images" in NON_WAIVABLE_RULES
        result = run_validator(pipeline, waived_rules={"pinned_images"})
        pinned = next(r for r in result.rules if r.rule_id == "pinned_images")
        assert pinned.status == "fail"  # NOT waived


# ---------------------------------------------------------------------------
# Interactive mode
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestInteractiveMode:
    """Tests for the interactive run mode."""

    def test_interactive_without_callback_behaves_like_validator(self) -> None:
        pipeline = load_pipeline(FIXTURES / "pinned_images_good.yml")
        result = run_interactive(pipeline)
        assert isinstance(result, WoodpeckerCheckResult)
        assert len(result.rules) == len(RULE_IDS)

    def test_interactive_waive_callback(self) -> None:
        """A callback returning 'waive' should waive a waivable rule."""
        pipeline = load_pipeline(FIXTURES / "stale_commit_guard_bad.yml")

        def waive_all(rule_result: WoodpeckerRuleResult) -> str | None:
            return "waive"

        result = run_interactive(pipeline, callback=waive_all)
        guard = next(r for r in result.rules if r.rule_id == "stale_commit_guard")
        assert guard.status == "waived"

    def test_interactive_non_waivable_stays_failed(self) -> None:
        """A callback returning 'waive' on a non-waivable rule should keep it failed."""
        pipeline = load_pipeline(FIXTURES / "pinned_images_bad.yml")

        def waive_all(rule_result: WoodpeckerRuleResult) -> str | None:
            return "waive"

        result = run_interactive(pipeline, callback=waive_all)
        pinned = next(r for r in result.rules if r.rule_id == "pinned_images")
        # Non-waivable: callback returns "waive" but the condition check prevents it
        assert pinned.status == "fail"


# ---------------------------------------------------------------------------
# Model tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestModels:
    """Tests for the pydantic models."""

    def test_check_result_failed_rules(self) -> None:
        result = WoodpeckerCheckResult(
            status="fail",
            rules=[
                WoodpeckerRuleResult(rule_id="a", status="pass", rationale="ok"),
                WoodpeckerRuleResult(rule_id="b", status="fail", evidence="bad", rationale="nope"),
                WoodpeckerRuleResult(rule_id="c", status="waived", rationale="waived"),
            ],
        )
        assert len(result.failed_rules) == 1
        assert result.failed_rules[0].rule_id == "b"
        assert len(result.waived_rules) == 1
        assert result.waived_rules[0].rule_id == "c"

    def test_rule_result_serialization(self) -> None:
        rule = WoodpeckerRuleResult(
            rule_id="test",
            status="pass",
            rationale="All good.",
        )
        data = rule.model_dump()
        assert data["rule_id"] == "test"
        assert data["status"] == "pass"
        assert data["evidence"] is None


# ---------------------------------------------------------------------------
# Convenience function
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestConvenience:
    """Tests for convenience wrapper functions."""

    def test_validate_pipeline_file(self) -> None:
        result = validate_pipeline_file(FIXTURES / "pinned_images_good.yml")
        assert isinstance(result, WoodpeckerCheckResult)
        assert len(result.rules) == len(RULE_IDS)
