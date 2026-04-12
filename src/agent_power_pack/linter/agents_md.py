"""AGENTS.md linter orchestrator (T038).

Top-level function that loads the document and runs all checks.
"""

from __future__ import annotations

import time
from pathlib import Path

from agent_power_pack.linter.document import load_agents_md
from agent_power_pack.linter.generated_check import check_generated
from agent_power_pack.linter.repo_check import check_repo
from agent_power_pack.linter.result import LintCheck, LintResult
from agent_power_pack.linter.schema_check import check_schema


def lint_agents_md(repo_root: Path, fix: bool = False) -> LintResult:
    """Lint AGENTS.md and return a structured result."""
    start = time.monotonic()

    agents_md_path = repo_root / "AGENTS.md"
    if not agents_md_path.exists():
        elapsed = int((time.monotonic() - start) * 1000)
        return LintResult(
            status="fail",
            checks=[
                LintCheck(
                    rule_id="schema.required_section",
                    status="fail",
                    message="AGENTS.md not found in repo root",
                )
            ],
            duration_ms=elapsed,
        )

    doc = load_agents_md(agents_md_path)

    # Optionally auto-fix generated files before checking
    if fix:
        from agent_power_pack.generator.revert import revert_hand_edits

        revert_hand_edits(repo_root)

    checks: list[LintCheck] = []
    checks.extend(check_schema(doc))
    checks.extend(check_repo(doc, repo_root))
    checks.extend(check_generated(doc, repo_root))

    has_fail = any(c.status == "fail" for c in checks)
    elapsed = int((time.monotonic() - start) * 1000)

    return LintResult(
        status="fail" if has_fail else "pass",
        checks=checks,
        duration_ms=elapsed,
    )
