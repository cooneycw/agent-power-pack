"""Woodpecker CI/CD checklist validator (FR-017/FR-018).

Parses `.woodpecker.yml` with ruamel.yaml and evaluates each rule from the
cooneycw/woodpecker-baseline findings as a pure function.  Rules are registered
in a dict keyed by rule ID so the checklist doubles as documentation.

Two run modes:
  - **Interactive** (cicd:woodpecker-checklist): walks the user through each
    rule with pass/fail/waive/explain.
  - **Validator** (cicd:init): runs all rules non-interactively, emits a JSON
    report, exits non-zero on any non-waivable failure.
"""

from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Any, Callable

from ruamel.yaml import YAML

from agent_power_pack.cicd.woodpecker_checklist_models import (
    WoodpeckerCheckResult,
    WoodpeckerRuleResult,
)
from agent_power_pack.logging import get_logger

log = get_logger("cicd.woodpecker_checklist")

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

RuleEvaluator = Callable[[dict[str, Any]], WoodpeckerRuleResult]
"""A pure function that takes a parsed pipeline dict and returns a rule result."""

# ---------------------------------------------------------------------------
# YAML loading
# ---------------------------------------------------------------------------


def load_pipeline(path: Path) -> dict[str, Any]:
    """Load a .woodpecker.yml file into a dict."""
    yaml = YAML(typ="safe")
    data = yaml.load(path)
    if not isinstance(data, dict):
        msg = f"Expected a YAML mapping at top level, got {type(data).__name__}"
        raise ValueError(msg)
    return data


def load_pipeline_from_string(text: str) -> dict[str, Any]:
    """Load a pipeline from a YAML string (for testing)."""
    yaml = YAML(typ="safe")
    data = yaml.load(text)
    if not isinstance(data, dict):
        msg = f"Expected a YAML mapping at top level, got {type(data).__name__}"
        raise ValueError(msg)
    return data


# ---------------------------------------------------------------------------
# Helper: iterate over all steps in a pipeline
# ---------------------------------------------------------------------------


def _iter_steps(pipeline: dict[str, Any]) -> list[tuple[str, str, dict[str, Any]]]:
    """Yield (pipeline_name, step_name, step_dict) for every step in every pipeline."""
    results: list[tuple[str, str, dict[str, Any]]] = []
    # Woodpecker v2 uses top-level keys as pipeline names, each containing a list of steps
    # or a dict with 'steps' key.
    for pipe_name, pipe_val in pipeline.items():
        if isinstance(pipe_val, list):
            # Each item is a step dict
            for step in pipe_val:
                if isinstance(step, dict):
                    step_name = step.get("name", "<unnamed>")
                    results.append((pipe_name, step_name, step))
        elif isinstance(pipe_val, dict):
            steps = pipe_val.get("steps", [])
            if isinstance(steps, list):
                for step in steps:
                    if isinstance(step, dict):
                        step_name = step.get("name", "<unnamed>")
                        results.append((pipe_name, step_name, step))
            # Also check if pipe_val itself looks like a step (has 'image' key)
            if "image" in pipe_val:
                results.append((pipe_name, pipe_name, pipe_val))
    return results


# ---------------------------------------------------------------------------
# Rule: pinned_images — no :latest tags
# ---------------------------------------------------------------------------

_LATEST_RE = re.compile(r":latest$")


def rule_pinned_images(pipeline: dict[str, Any]) -> WoodpeckerRuleResult:
    """Every container image must use a pinned tag, never :latest."""
    violations: list[str] = []
    for pipe_name, step_name, step in _iter_steps(pipeline):
        image = step.get("image", "")
        if isinstance(image, str):
            # No tag at all implies :latest; explicit :latest also fails
            if _LATEST_RE.search(image) or (":" not in image and "/" in image):
                violations.append(f"{pipe_name}.{step_name}: image={image}")
    if violations:
        return WoodpeckerRuleResult(
            rule_id="pinned_images",
            status="fail",
            evidence="; ".join(violations),
            rationale="Unpinned images cause non-reproducible builds. Always pin to a specific tag or SHA.",
        )
    return WoodpeckerRuleResult(
        rule_id="pinned_images",
        status="pass",
        rationale="All images use pinned tags.",
    )


# ---------------------------------------------------------------------------
# Rule: safe_directory — git config safe.directory for root-in-container
# ---------------------------------------------------------------------------


def rule_safe_directory(pipeline: dict[str, Any]) -> WoodpeckerRuleResult:
    """Pipeline must set git config --global safe.directory for root-in-container git ops."""
    all_commands: list[str] = []
    for _, _, step in _iter_steps(pipeline):
        commands = step.get("commands", [])
        if isinstance(commands, list):
            all_commands.extend(str(c) for c in commands)
    joined = " ".join(all_commands)
    if "safe.directory" in joined:
        return WoodpeckerRuleResult(
            rule_id="safe_directory",
            status="pass",
            rationale="safe.directory is configured for root-in-container git operations.",
        )
    # Check if any step uses git commands
    has_git = any("git " in c for c in all_commands)
    if not has_git:
        return WoodpeckerRuleResult(
            rule_id="safe_directory",
            status="pass",
            rationale="No git commands found; safe.directory not required.",
        )
    return WoodpeckerRuleResult(
        rule_id="safe_directory",
        status="fail",
        evidence="Git commands found but no `git config --global safe.directory` set.",
        rationale="Woodpecker runs as root inside containers. Git refuses to operate on "
        "directories owned by other users unless safe.directory is configured.",
    )


# ---------------------------------------------------------------------------
# Rule: no_unjustified_failure_ignore
# ---------------------------------------------------------------------------


def rule_no_unjustified_failure_ignore(pipeline: dict[str, Any]) -> WoodpeckerRuleResult:
    """No step should use failure: ignore without a documented justification."""
    violations: list[str] = []
    for pipe_name, step_name, step in _iter_steps(pipeline):
        failure = step.get("failure")
        if failure == "ignore":
            # Check for a comment-like justification in the step name or a
            # 'failure_justification' custom field
            justification = step.get("failure_justification", "")
            if not justification:
                violations.append(f"{pipe_name}.{step_name}")
    if violations:
        return WoodpeckerRuleResult(
            rule_id="no_unjustified_failure_ignore",
            status="fail",
            evidence=f"Steps with unjustified failure:ignore: {'; '.join(violations)}",
            rationale="failure:ignore silently swallows real errors. Every use must include "
            "a failure_justification field explaining why it's safe.",
        )
    return WoodpeckerRuleResult(
        rule_id="no_unjustified_failure_ignore",
        status="pass",
        rationale="No unjustified failure:ignore found.",
    )


# ---------------------------------------------------------------------------
# Rule: stale_commit_guard — deploy scripts must check for stale commits
# ---------------------------------------------------------------------------


def rule_stale_commit_guard(pipeline: dict[str, Any]) -> WoodpeckerRuleResult:
    """Deploy steps must include a stale-commit guard (fetch + compare before deploy)."""
    deploy_steps: list[tuple[str, str, dict[str, Any]]] = []
    for pipe_name, step_name, step in _iter_steps(pipeline):
        commands = step.get("commands", [])
        name_lower = step_name.lower()
        cmds_joined = " ".join(str(c) for c in commands) if isinstance(commands, list) else ""
        if "deploy" in name_lower or "deploy" in cmds_joined:
            deploy_steps.append((pipe_name, step_name, step))

    if not deploy_steps:
        return WoodpeckerRuleResult(
            rule_id="stale_commit_guard",
            status="pass",
            rationale="No deploy steps found; stale-commit guard not required.",
        )

    for pipe_name, step_name, step in deploy_steps:
        commands = step.get("commands", [])
        cmds_joined = " ".join(str(c) for c in commands) if isinstance(commands, list) else ""
        if "git fetch" in cmds_joined or "stale" in cmds_joined.lower():
            continue
        return WoodpeckerRuleResult(
            rule_id="stale_commit_guard",
            status="fail",
            evidence=f"{pipe_name}.{step_name} deploys without a stale-commit check.",
            rationale="Without a stale-commit guard, a slow pipeline can deploy an outdated "
            "commit over a newer one. Always fetch and compare before deploying.",
        )

    return WoodpeckerRuleResult(
        rule_id="stale_commit_guard",
        status="pass",
        rationale="All deploy steps include a stale-commit guard.",
    )


# ---------------------------------------------------------------------------
# Rule: concurrent_deploy_lock
# ---------------------------------------------------------------------------


def rule_concurrent_deploy_lock(pipeline: dict[str, Any]) -> WoodpeckerRuleResult:
    """Deploy pipelines must declare a concurrency lock with a documented protected resource."""
    # Check for top-level 'labels' with deploy-related keys, or 'when' constraints
    deploy_pipes: list[str] = []
    for pipe_name, pipe_val in pipeline.items():
        if "deploy" in pipe_name.lower():
            deploy_pipes.append(pipe_name)

    if not deploy_pipes:
        return WoodpeckerRuleResult(
            rule_id="concurrent_deploy_lock",
            status="pass",
            rationale="No deploy pipelines found; concurrency lock not required.",
        )

    for pipe_name in deploy_pipes:
        pipe_val = pipeline[pipe_name]
        if not isinstance(pipe_val, dict):
            continue
        # Check for concurrency or max_concurrent or depends_on serialization
        if "concurrency" not in pipe_val and "max_concurrent" not in pipe_val:
            return WoodpeckerRuleResult(
                rule_id="concurrent_deploy_lock",
                status="fail",
                evidence=f"Pipeline '{pipe_name}' has no concurrency lock.",
                rationale="Concurrent deploys to the same target cause race conditions. "
                "Add a concurrency key with a documented protected resource.",
            )

    return WoodpeckerRuleResult(
        rule_id="concurrent_deploy_lock",
        status="pass",
        rationale="All deploy pipelines declare concurrency locks.",
    )


# ---------------------------------------------------------------------------
# Rule: two_phase_readiness — liveness + capability probes with proxy buffer
# ---------------------------------------------------------------------------


def rule_two_phase_readiness(pipeline: dict[str, Any]) -> WoodpeckerRuleResult:
    """Deploy steps should include two-phase readiness checks (liveness + capability)."""
    deploy_steps: list[tuple[str, str, dict[str, Any]]] = []
    for pipe_name, step_name, step in _iter_steps(pipeline):
        name_lower = step_name.lower()
        commands = step.get("commands", [])
        cmds_joined = " ".join(str(c) for c in commands) if isinstance(commands, list) else ""
        if "deploy" in name_lower or "deploy" in cmds_joined:
            deploy_steps.append((pipe_name, step_name, step))

    if not deploy_steps:
        return WoodpeckerRuleResult(
            rule_id="two_phase_readiness",
            status="pass",
            rationale="No deploy steps found; readiness checks not required.",
        )

    for pipe_name, step_name, step in deploy_steps:
        commands = step.get("commands", [])
        cmds_joined = " ".join(str(c) for c in commands) if isinstance(commands, list) else ""
        has_health = "health" in cmds_joined.lower() or "readiness" in cmds_joined.lower()
        has_curl = "curl" in cmds_joined
        has_wait = "sleep" in cmds_joined or "wait" in cmds_joined.lower()
        if not (has_health or has_curl) or not has_wait:
            return WoodpeckerRuleResult(
                rule_id="two_phase_readiness",
                status="fail",
                evidence=f"{pipe_name}.{step_name} lacks two-phase readiness (health check + wait buffer).",
                rationale="Services need time to become ready after deploy. Use a liveness "
                "probe (health check endpoint) plus a wait buffer for reverse-proxy propagation.",
            )

    return WoodpeckerRuleResult(
        rule_id="two_phase_readiness",
        status="pass",
        rationale="Deploy steps include two-phase readiness checks.",
    )


# ---------------------------------------------------------------------------
# Rule: secrets_readable_first_step
# ---------------------------------------------------------------------------


def rule_secrets_readable_first_step(pipeline: dict[str, Any]) -> WoodpeckerRuleResult:
    """Secrets should be validated in the first step of any pipeline that uses them."""
    for pipe_name, pipe_val in pipeline.items():
        if not isinstance(pipe_val, (dict, list)):
            continue
        steps = pipe_val if isinstance(pipe_val, list) else pipe_val.get("steps", [])
        if not isinstance(steps, list) or not steps:
            continue

        # Collect all secrets references across all steps
        uses_secrets = False
        for step in steps:
            if not isinstance(step, dict):
                continue
            env = step.get("environment", {})
            if isinstance(env, dict):
                for val in env.values():
                    if isinstance(val, str) and "from_secret" in str(val):
                        uses_secrets = True
                        break
            secrets = step.get("secrets", [])
            if secrets:
                uses_secrets = True
            if uses_secrets:
                break

        if not uses_secrets:
            continue

        # Check first step validates secrets
        first_step = steps[0] if steps else {}
        if not isinstance(first_step, dict):
            continue
        first_cmds = first_step.get("commands", [])
        first_cmds_joined = " ".join(str(c) for c in first_cmds) if isinstance(first_cmds, list) else ""
        if "secret" not in first_cmds_joined.lower() and "env" not in first_cmds_joined.lower():
            return WoodpeckerRuleResult(
                rule_id="secrets_readable_first_step",
                status="fail",
                evidence=f"Pipeline '{pipe_name}' uses secrets but first step doesn't validate them.",
                rationale="Validate secrets are readable in the first step so failures are "
                "caught early with a clear error, not mid-deploy.",
            )

    return WoodpeckerRuleResult(
        rule_id="secrets_readable_first_step",
        status="pass",
        rationale="Secrets are validated early or not used.",
    )


# ---------------------------------------------------------------------------
# Rule: explicit_when_depends_on
# ---------------------------------------------------------------------------


def rule_explicit_when_depends_on(pipeline: dict[str, Any]) -> WoodpeckerRuleResult:
    """Steps must use explicit `when` filters and `depends_on`, not rely on sequential naming."""
    steps_without_when: list[str] = []
    total_steps = 0
    for pipe_name, step_name, step in _iter_steps(pipeline):
        total_steps += 1
        has_when = "when" in step
        has_depends = "depends_on" in step
        # First step in a pipeline doesn't need depends_on
        # but non-first steps should have explicit ordering
        if not has_when and not has_depends and total_steps > 1:
            steps_without_when.append(f"{pipe_name}.{step_name}")

    if steps_without_when:
        return WoodpeckerRuleResult(
            rule_id="explicit_when_depends_on",
            status="fail",
            evidence=f"Steps without explicit when/depends_on: {'; '.join(steps_without_when)}",
            rationale="Relying on YAML key order for step execution is fragile. "
            "Use explicit `when` filters and `depends_on` to declare intent.",
        )
    return WoodpeckerRuleResult(
        rule_id="explicit_when_depends_on",
        status="pass",
        rationale="All steps use explicit when/depends_on.",
    )


# ---------------------------------------------------------------------------
# Rule: required_agent_labels
# ---------------------------------------------------------------------------


def rule_required_agent_labels(pipeline: dict[str, Any]) -> WoodpeckerRuleResult:
    """Privileged deploy pipelines must specify required agent labels."""
    for pipe_name, pipe_val in pipeline.items():
        if not isinstance(pipe_val, dict):
            continue
        if "deploy" not in pipe_name.lower():
            continue
        labels = pipe_val.get("labels", {})
        platform = pipe_val.get("platform", "")
        if not labels and not platform:
            return WoodpeckerRuleResult(
                rule_id="required_agent_labels",
                status="fail",
                evidence=f"Deploy pipeline '{pipe_name}' has no agent labels.",
                rationale="Without agent labels, a deploy pipeline may run on any agent, "
                "including ones without access to the target environment. "
                "Specify labels to pin deploys to authorized agents.",
            )

    return WoodpeckerRuleResult(
        rule_id="required_agent_labels",
        status="pass",
        rationale="Deploy pipelines specify agent labels or no deploy pipelines found.",
    )


# ---------------------------------------------------------------------------
# Rule: pre_merge_non_prod_test
# ---------------------------------------------------------------------------


def rule_pre_merge_non_prod_test(pipeline: dict[str, Any]) -> WoodpeckerRuleResult:
    """There should be a test/staging deploy that runs before production deploy."""
    has_test_deploy = False
    has_prod_deploy = False

    for pipe_name in pipeline:
        name_lower = pipe_name.lower()
        if any(kw in name_lower for kw in ("test", "staging", "stage", "dev", "preview")):
            pipe_val = pipeline[pipe_name]
            if isinstance(pipe_val, dict):
                steps = pipe_val.get("steps", [])
            elif isinstance(pipe_val, list):
                steps = pipe_val
            else:
                steps = []
            for step in steps if isinstance(steps, list) else []:
                if isinstance(step, dict):
                    cmds = " ".join(str(c) for c in step.get("commands", []))
                    if "deploy" in cmds.lower() or "deploy" in step.get("name", "").lower():
                        has_test_deploy = True
        if any(kw in name_lower for kw in ("prod", "production", "release")):
            has_prod_deploy = True

    if has_prod_deploy and not has_test_deploy:
        return WoodpeckerRuleResult(
            rule_id="pre_merge_non_prod_test",
            status="fail",
            evidence="Production deploy pipeline found but no test/staging deploy pipeline.",
            rationale="Always deploy to a non-production environment first to catch "
            "issues before they reach production.",
        )

    return WoodpeckerRuleResult(
        rule_id="pre_merge_non_prod_test",
        status="pass",
        rationale="Test/staging deploy precedes production, or no production deploy found.",
    )


# ---------------------------------------------------------------------------
# Rule: artifact_validation_gate — build artifacts must be validated before promotion
# ---------------------------------------------------------------------------

_BUILD_KEYWORDS = ("build", "bake", "compile", "package", "bundle", "assemble")
_VALIDATE_KEYWORDS = ("validate", "contract", "canary", "verify", "smoke", "test-artifact", "check-artifact")


def rule_artifact_validation_gate(pipeline: dict[str, Any]) -> WoodpeckerRuleResult:
    """Build/bake steps that produce artifacts must have a validation step before promotion."""
    all_steps = _iter_steps(pipeline)

    # Find steps that produce artifacts (build/bake steps)
    build_step_indices: list[tuple[int, str, str]] = []
    promote_step_indices: list[tuple[int, str, str]] = []
    validate_step_indices: list[int] = []

    for idx, (pipe_name, step_name, step) in enumerate(all_steps):
        name_lower = step_name.lower()
        commands = step.get("commands", [])
        cmds_joined = " ".join(str(c) for c in commands) if isinstance(commands, list) else ""
        combined = f"{name_lower} {cmds_joined.lower()}"

        if any(kw in combined for kw in _BUILD_KEYWORDS):
            build_step_indices.append((idx, pipe_name, step_name))
        if any(kw in combined for kw in ("push", "promote", "publish", "release", "deploy")):
            promote_step_indices.append((idx, pipe_name, step_name))
        if any(kw in combined for kw in _VALIDATE_KEYWORDS):
            validate_step_indices.append(idx)

    # No build steps → rule not applicable
    if not build_step_indices:
        return WoodpeckerRuleResult(
            rule_id="artifact_validation_gate",
            status="pass",
            rationale="No build/bake steps found; artifact validation gate not required.",
        )

    # No promote steps → rule not applicable (artifact isn't being promoted)
    if not promote_step_indices:
        return WoodpeckerRuleResult(
            rule_id="artifact_validation_gate",
            status="pass",
            rationale="No promotion steps found; artifact validation gate not required.",
        )

    # Check: there should be a validation step between build and promote
    for build_idx, build_pipe, build_step in build_step_indices:
        for promote_idx, promote_pipe, promote_step in promote_step_indices:
            if promote_idx > build_idx:
                has_validation_between = any(
                    build_idx < v_idx < promote_idx for v_idx in validate_step_indices
                )
                if not has_validation_between:
                    return WoodpeckerRuleResult(
                        rule_id="artifact_validation_gate",
                        status="fail",
                        evidence=(
                            f"Build step '{build_pipe}.{build_step}' is promoted by "
                            f"'{promote_pipe}.{promote_step}' with no validation gate between them."
                        ),
                        rationale=(
                            "Artifacts (images, AMIs, bundles) should be validated before promotion. "
                            "Add a validation step (smoke test, contract check, canary) between "
                            "build and push/promote to catch broken artifacts before they reach production."
                        ),
                    )

    return WoodpeckerRuleResult(
        rule_id="artifact_validation_gate",
        status="pass",
        rationale="Build artifacts are validated before promotion.",
    )


# ---------------------------------------------------------------------------
# Rule: explicit_runtime_contracts — deploy steps should validate environment
# ---------------------------------------------------------------------------

_INSTALL_KEYWORDS = ("apt", "apk", "pip", "npm", "yarn", "pnpm", "dnf", "yum", "pacman")
_CONTRACT_KEYWORDS = ("contract", "validate-runtime", "validate-env", "check-runtime", "runtime-check", "preflight")


def rule_explicit_runtime_contracts(pipeline: dict[str, Any]) -> WoodpeckerRuleResult:
    """Deploy steps that install software should validate the runtime environment explicitly."""
    violations: list[str] = []

    for pipe_name, step_name, step in _iter_steps(pipeline):
        name_lower = step_name.lower()
        commands = step.get("commands", [])
        cmds_joined = " ".join(str(c) for c in commands) if isinstance(commands, list) else ""
        combined = f"{name_lower} {cmds_joined.lower()}"

        # Only check deploy-related steps that install packages
        is_deploy = "deploy" in combined
        has_install = any(f"{kw} install" in cmds_joined.lower() or f"{kw} add" in cmds_joined.lower() for kw in _INSTALL_KEYWORDS)

        if is_deploy and has_install:
            has_contract = any(kw in combined for kw in _CONTRACT_KEYWORDS)
            if not has_contract:
                violations.append(f"{pipe_name}.{step_name}")

    if not violations:
        return WoodpeckerRuleResult(
            rule_id="explicit_runtime_contracts",
            status="pass",
            rationale="Deploy steps validate runtime environment or do not install packages.",
        )

    return WoodpeckerRuleResult(
        rule_id="explicit_runtime_contracts",
        status="fail",
        evidence=f"Deploy steps install packages without runtime contract validation: {'; '.join(violations)}",
        rationale=(
            "When deploy steps install system packages (apt, apk, pip, npm), the runtime environment "
            "should be validated with an explicit contract script. Implicit assumptions about "
            "available packages/versions fail silently. Add a preflight or contract validation step."
        ),
    )


# ---------------------------------------------------------------------------
# Rule: canary_before_fleet — fleet-wide operations need a canary step
# ---------------------------------------------------------------------------

_FLEET_KEYWORDS = (
    "asg", "autoscaling", "desired-capacity", "rolling-update", "rollout",
    "kubectl rollout", "fleet", "scale-up", "scale-out",
)
_CANARY_KEYWORDS = ("canary", "single-target", "single-instance", "blue-green", "one-box", "validate-canary")


def rule_canary_before_fleet(pipeline: dict[str, Any]) -> WoodpeckerRuleResult:
    """Fleet-wide operations (ASG refresh, rolling deploy) must have a canary/single-target step first."""
    all_steps = _iter_steps(pipeline)

    fleet_steps: list[tuple[int, str, str]] = []
    canary_indices: list[int] = []

    for idx, (pipe_name, step_name, step) in enumerate(all_steps):
        name_lower = step_name.lower()
        commands = step.get("commands", [])
        cmds_joined = " ".join(str(c) for c in commands) if isinstance(commands, list) else ""
        combined = f"{name_lower} {cmds_joined.lower()}"

        if any(kw in combined for kw in _FLEET_KEYWORDS):
            fleet_steps.append((idx, pipe_name, step_name))
        if any(kw in combined for kw in _CANARY_KEYWORDS):
            canary_indices.append(idx)

    if not fleet_steps:
        return WoodpeckerRuleResult(
            rule_id="canary_before_fleet",
            status="pass",
            rationale="No fleet-wide operations found; canary step not required.",
        )

    for fleet_idx, fleet_pipe, fleet_step in fleet_steps:
        has_canary_before = any(c_idx < fleet_idx for c_idx in canary_indices)
        if not has_canary_before:
            return WoodpeckerRuleResult(
                rule_id="canary_before_fleet",
                status="fail",
                evidence=(
                    f"Fleet operation '{fleet_pipe}.{fleet_step}' has no canary/single-target "
                    f"step preceding it."
                ),
                rationale=(
                    "Fleet-wide operations (ASG refresh, rolling deploys, kubectl rollout) affect "
                    "all instances simultaneously. A canary or single-target step must validate "
                    "the change on one instance before promoting to the entire fleet."
                ),
            )

    return WoodpeckerRuleResult(
        rule_id="canary_before_fleet",
        status="pass",
        rationale="Fleet operations are preceded by canary/single-target validation.",
    )


# ---------------------------------------------------------------------------
# Rule registry
# ---------------------------------------------------------------------------

RULE_REGISTRY: dict[str, RuleEvaluator] = {
    "pinned_images": rule_pinned_images,
    "safe_directory": rule_safe_directory,
    "no_unjustified_failure_ignore": rule_no_unjustified_failure_ignore,
    "stale_commit_guard": rule_stale_commit_guard,
    "concurrent_deploy_lock": rule_concurrent_deploy_lock,
    "two_phase_readiness": rule_two_phase_readiness,
    "secrets_readable_first_step": rule_secrets_readable_first_step,
    "explicit_when_depends_on": rule_explicit_when_depends_on,
    "required_agent_labels": rule_required_agent_labels,
    "pre_merge_non_prod_test": rule_pre_merge_non_prod_test,
    "artifact_validation_gate": rule_artifact_validation_gate,
    "explicit_runtime_contracts": rule_explicit_runtime_contracts,
    "canary_before_fleet": rule_canary_before_fleet,
}

# Rules that cannot be waived — failure is always blocking
NON_WAIVABLE_RULES: frozenset[str] = frozenset({
    "pinned_images",
    "safe_directory",
    "no_unjustified_failure_ignore",
})


# ---------------------------------------------------------------------------
# Run modes
# ---------------------------------------------------------------------------


def run_validator(
    pipeline: dict[str, Any],
    *,
    waived_rules: set[str] | None = None,
) -> WoodpeckerCheckResult:
    """Non-interactive validator mode: run all rules, return structured result.

    Used by cicd:init (FR-018) as a gate.  Exits non-zero on any non-waivable failure.
    """
    start = time.monotonic()
    waived = waived_rules or set()
    results: list[WoodpeckerRuleResult] = []

    for rule_id, evaluator in RULE_REGISTRY.items():
        result = evaluator(pipeline)
        # Apply waiver if rule is waivable and was waived
        if result.status == "fail" and rule_id in waived and rule_id not in NON_WAIVABLE_RULES:
            result = WoodpeckerRuleResult(
                rule_id=rule_id,
                status="waived",
                evidence=result.evidence,
                rationale=result.rationale,
            )
        results.append(result)

    has_failures = any(r.status == "fail" for r in results)
    duration_ms = int((time.monotonic() - start) * 1000)
    log.info(
        "woodpecker_checklist_complete",
        status="fail" if has_failures else "pass",
        duration_ms=duration_ms,
        rules_evaluated=len(results),
        rules_failed=sum(1 for r in results if r.status == "fail"),
        rules_waived=sum(1 for r in results if r.status == "waived"),
    )

    return WoodpeckerCheckResult(
        status="fail" if has_failures else "pass",
        rules=results,
    )


def run_interactive(
    pipeline: dict[str, Any],
    *,
    callback: Callable[[WoodpeckerRuleResult], str | None] | None = None,
) -> WoodpeckerCheckResult:
    """Interactive mode: walk the user through each rule.

    The callback receives each rule result and returns:
      - None or "accept" to accept the result as-is
      - "waive" to waive a failed rule (only if waivable)
      - "explain" to get the rationale (then re-prompt)

    If no callback is provided, behaves like validator mode.
    """
    results: list[WoodpeckerRuleResult] = []

    for rule_id, evaluator in RULE_REGISTRY.items():
        result = evaluator(pipeline)

        if callback and result.status == "fail":
            while True:
                action = callback(result)
                if action == "explain":
                    # Caller handles display; re-prompt
                    continue
                if action == "waive" and rule_id not in NON_WAIVABLE_RULES:
                    result = WoodpeckerRuleResult(
                        rule_id=rule_id,
                        status="waived",
                        evidence=result.evidence,
                        rationale=result.rationale,
                    )
                break

        results.append(result)

    has_failures = any(r.status == "fail" for r in results)
    return WoodpeckerCheckResult(
        status="fail" if has_failures else "pass",
        rules=results,
    )


def validate_pipeline_file(path: Path, *, waived_rules: set[str] | None = None) -> WoodpeckerCheckResult:
    """Convenience: load a file and run the validator."""
    pipeline = load_pipeline(path)
    return run_validator(pipeline, waived_rules=waived_rules)
