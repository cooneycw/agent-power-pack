"""Schema check: verify required H2 sections in AGENTS.md (T034)."""

from __future__ import annotations

from agent_power_pack.linter.document import AgentsMdDocument
from agent_power_pack.linter.result import LintCheck

REQUIRED_SECTIONS = [
    "CI/CD Protocol",
    "Quality Gates",
    "Troubleshooting",
    "Available Commands",
    "Docker Conventions",
    "Deployment",
]


def check_schema(doc: AgentsMdDocument) -> list[LintCheck]:
    """Return one LintCheck per required section, plus an overall check."""
    checks: list[LintCheck] = []
    all_present = True

    for section in REQUIRED_SECTIONS:
        present = section in doc.sections
        if not present:
            all_present = False
        checks.append(
            LintCheck(
                rule_id="schema.required_section",
                status="pass" if present else "fail",
                message=f"Required section '{section}' {'found' if present else 'missing'}",
                subject=section,
            )
        )

    checks.append(
        LintCheck(
            rule_id="schema.required_section",
            status="pass" if all_present else "fail",
            message="All required sections present" if all_present else "One or more required sections missing",
        )
    )

    return checks
