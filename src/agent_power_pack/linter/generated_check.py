"""Generated-file check: verify CLAUDE.md, GEMINI.md, .cursorrules are in sync (T036)."""

from __future__ import annotations

from pathlib import Path

from agent_power_pack.linter.document import AgentsMdDocument
from agent_power_pack.linter.result import LintCheck

GENERATED_HEADER = "<!-- GENERATED FROM AGENTS.md \u2014 DO NOT EDIT -->"
HASH_PREFIX = "<!-- source-hash: "

GENERATED_FILES = ["CLAUDE.md", "GEMINI.md", ".cursorrules"]


def check_generated(doc: AgentsMdDocument, repo_root: Path) -> list[LintCheck]:
    """Check that generated instruction files are in sync with AGENTS.md."""
    checks: list[LintCheck] = []

    for filename in GENERATED_FILES:
        path = repo_root / filename
        if not path.exists():
            # File doesn't exist — skip (not an error)
            continue

        text = path.read_text()
        lines = text.splitlines()

        # Check header
        if not lines or lines[0].strip() != GENERATED_HEADER:
            checks.append(
                LintCheck(
                    rule_id="generated.header_present",
                    status="fail",
                    message=f"{filename} missing generated header",
                    subject=filename,
                )
            )
            checks.append(
                LintCheck(
                    rule_id="generated.in_sync",
                    status="fail",
                    message=f"{filename} appears hand-edited (no header)",
                    subject=filename,
                )
            )
            continue

        checks.append(
            LintCheck(
                rule_id="generated.header_present",
                status="pass",
                message=f"{filename} has generated header",
                subject=filename,
            )
        )

        # Check hash
        if len(lines) >= 2 and lines[1].strip().startswith(HASH_PREFIX):
            file_hash = lines[1].strip().removeprefix(HASH_PREFIX).removesuffix(" -->")
            if file_hash == doc.content_hash:
                checks.append(
                    LintCheck(
                        rule_id="generated.in_sync",
                        status="pass",
                        message=f"{filename} is in sync with AGENTS.md",
                        subject=filename,
                    )
                )
            else:
                checks.append(
                    LintCheck(
                        rule_id="generated.in_sync",
                        status="fail",
                        message=f"{filename} hash mismatch (stale)",
                        subject=filename,
                    )
                )
        else:
            checks.append(
                LintCheck(
                    rule_id="generated.in_sync",
                    status="fail",
                    message=f"{filename} missing source-hash comment",
                    subject=filename,
                )
            )

    return checks
