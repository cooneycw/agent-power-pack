"""Revert hand-edits to generated instruction files (T040)."""

from __future__ import annotations

from pathlib import Path

from agent_power_pack.linter.generated_check import GENERATED_FILES, GENERATED_HEADER, HASH_PREFIX
from agent_power_pack.linter.document import load_agents_md
from agent_power_pack.linter.result import LintCheck


def revert_hand_edits(repo_root: Path) -> list[LintCheck]:
    """Regenerate any hand-edited instruction files. Returns warn checks for reverted files."""
    agents_md = repo_root / "AGENTS.md"
    if not agents_md.exists():
        return []

    doc = load_agents_md(agents_md)
    content = agents_md.read_text()
    checks: list[LintCheck] = []

    for filename in GENERATED_FILES:
        path = repo_root / filename
        if not path.exists():
            continue

        text = path.read_text()
        lines = text.splitlines()

        needs_revert = False
        if not lines or lines[0].strip() != GENERATED_HEADER:
            needs_revert = True
        elif len(lines) >= 2 and lines[1].strip().startswith(HASH_PREFIX):
            file_hash = lines[1].strip().removeprefix(HASH_PREFIX).removesuffix(" -->")
            if file_hash != doc.content_hash:
                needs_revert = True
        else:
            needs_revert = True

        if needs_revert:
            path.write_text(
                f"{GENERATED_HEADER}\n"
                f"{HASH_PREFIX}{doc.content_hash} -->\n"
                f"{content}"
            )
            checks.append(
                LintCheck(
                    rule_id="generated.in_sync",
                    status="warn",
                    message=f"{filename} was hand-edited; reverted to AGENTS.md content",
                    subject=filename,
                )
            )

    return checks
