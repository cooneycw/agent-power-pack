"""Git-based staleness detection for documentation artifacts (spec 002, FR-011/012/013/014).

Compares HEAD against ``last_commit_sha`` per artifact in ``docs/plan.yaml``,
maps changed files to artifacts via ``source_signals``, and supports issue
lifecycle for stale-docs nudges in ``flow:finish``.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import structlog

from agent_power_pack.docs.executor import get_current_sha, load_plan

logger = structlog.get_logger()

STALE_ISSUE_LABEL = "docs-stale"
STALE_ISSUE_TITLE_PREFIX = "Documentation stale"


@dataclass
class StaleArtifact:
    """An artifact whose source files have changed since last generation."""

    artifact_type: str
    name: str
    last_commit_sha: str | None
    changed_files: list[str] = field(default_factory=list)
    source_signals: list[str] = field(default_factory=list)


@dataclass
class StalenessResult:
    """Result of a staleness check across all artifacts in the plan."""

    stale: list[StaleArtifact] = field(default_factory=list)
    current: list[str] = field(default_factory=list)
    skipped: bool = False
    reason: str = ""

    @property
    def has_stale(self) -> bool:
        return len(self.stale) > 0


def _get_changed_files(project_root: Path, since_sha: str) -> list[str]:
    """Get files changed between ``since_sha`` and HEAD."""
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", f"{since_sha}..HEAD"],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=str(project_root),
        )
        if result.returncode == 0:
            return [f for f in result.stdout.strip().splitlines() if f]
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return []


def _signal_matches_file(signal: str, changed_file: str) -> bool:
    """Check if a changed file matches a source signal.

    A signal can be a file path (exact match) or a directory prefix.
    """
    if signal == changed_file:
        return True
    # Directory match: signal "src/" matches "src/foo/bar.py"
    signal_norm = signal.rstrip("/") + "/"
    return changed_file.startswith(signal_norm)


def detect_stale_artifacts(
    plan_path: Path,
    project_root: Path,
) -> StalenessResult:
    """Compare HEAD against ``last_commit_sha`` per artifact (FR-011).

    Returns a ``StalenessResult`` listing stale and current artifacts.
    If ``plan_path`` does not exist, returns a skipped result (FR-014).
    """
    if not plan_path.exists():
        return StalenessResult(skipped=True, reason="No docs/plan.yaml — staleness check skipped")

    plan = load_plan(plan_path)
    artifacts = plan.get("artifacts", [])
    if not artifacts:
        return StalenessResult(reason="No artifacts in plan")

    current_sha = get_current_sha(project_root)
    if not current_sha:
        return StalenessResult(reason="Could not determine current HEAD SHA")

    result = StalenessResult()

    for artifact in artifacts:
        art_type = artifact.get("type", "")
        art_name = artifact.get("name", art_type)
        last_sha = artifact.get("last_commit_sha")
        signals = artifact.get("source_signals", [])

        if not last_sha:
            # Never generated — always stale
            result.stale.append(StaleArtifact(
                artifact_type=art_type,
                name=art_name,
                last_commit_sha=None,
                changed_files=["(never generated)"],
                source_signals=signals,
            ))
            continue

        if last_sha == current_sha:
            result.current.append(art_type)
            continue

        # Check which source signals have changed files
        changed = _get_changed_files(project_root, last_sha)
        if not changed:
            result.current.append(art_type)
            continue

        matched_files = []
        for changed_file in changed:
            for signal in signals:
                if _signal_matches_file(signal, changed_file):
                    matched_files.append(changed_file)
                    break

        if matched_files:
            result.stale.append(StaleArtifact(
                artifact_type=art_type,
                name=art_name,
                last_commit_sha=last_sha,
                changed_files=matched_files,
                source_signals=signals,
            ))
        else:
            result.current.append(art_type)

    return result


def format_staleness_report(result: StalenessResult, project_root: Path) -> str:
    """Format a human-readable staleness report."""
    if result.skipped:
        return result.reason

    if not result.has_stale:
        return f"All {len(result.current)} artifacts are up to date."

    lines = [f"{len(result.stale)} stale artifact(s) detected:\n"]
    for sa in result.stale:
        lines.append(f"  - **{sa.name}** ({sa.artifact_type})")
        lines.append(f"    Last SHA: {sa.last_commit_sha or '(never generated)'}")
        lines.append(f"    Changed files: {', '.join(sa.changed_files[:5])}")
        if len(sa.changed_files) > 5:
            lines.append(f"    ... and {len(sa.changed_files) - 5} more")

    lines.append("\nTo regenerate: `agent-power-pack docs update`")
    return "\n".join(lines)


def _build_issue_body(result: StalenessResult) -> str:
    """Build the body for a docs-stale issue."""
    lines = ["Documentation artifacts are stale and need regeneration.\n"]
    lines.append("## Stale Artifacts\n")

    for sa in result.stale:
        lines.append(f"### {sa.name} (`{sa.artifact_type}`)")
        lines.append(f"- Last generated at: `{sa.last_commit_sha or 'never'}`")
        lines.append(f"- Source signals: {', '.join(sa.source_signals)}")
        lines.append("- Changed files:")
        for f in sa.changed_files[:10]:
            lines.append(f"  - `{f}`")
        if len(sa.changed_files) > 10:
            lines.append(f"  - ... and {len(sa.changed_files) - 10} more")
        lines.append("")

    lines.append("## How to fix\n")
    lines.append("```bash")
    lines.append("agent-power-pack docs update")
    lines.append("```")

    return "\n".join(lines)


def _build_comment_body(result: StalenessResult) -> str:
    """Build a comment body for an existing docs-stale issue."""
    lines = ["New staleness detected:\n"]
    for sa in result.stale:
        lines.append(f"- **{sa.name}** (`{sa.artifact_type}`): {len(sa.changed_files)} file(s) changed")
    return "\n".join(lines)


def find_open_stale_issue() -> int | None:
    """Find an existing open docs-stale issue via ``gh``.

    Returns the issue number or None.
    """
    try:
        result = subprocess.run(
            [
                "gh", "issue", "list",
                "--label", STALE_ISSUE_LABEL,
                "--state", "open",
                "--json", "number",
                "--jq", ".[0].number",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            return int(result.stdout.strip())
    except (subprocess.TimeoutExpired, FileNotFoundError, ValueError):
        pass
    return None


def create_or_update_stale_issue(result: StalenessResult) -> int | None:
    """Create or update a docs-stale issue (FR-013).

    Returns the issue number (created or existing), or None on failure.
    """
    if not result.has_stale:
        return None

    existing = find_open_stale_issue()

    if existing:
        # Add comment to existing issue
        comment = _build_comment_body(result)
        try:
            subprocess.run(
                ["gh", "issue", "comment", str(existing), "--body", comment],
                capture_output=True,
                text=True,
                timeout=10,
            )
            logger.info("Added comment to existing docs-stale issue", issue=existing)
        except (subprocess.TimeoutExpired, FileNotFoundError):
            logger.warning("Failed to comment on docs-stale issue", issue=existing)
        return existing

    # Create new issue
    title = f"{STALE_ISSUE_TITLE_PREFIX} — {len(result.stale)} artifact(s) need regeneration"
    body = _build_issue_body(result)
    try:
        create_result = subprocess.run(
            [
                "gh", "issue", "create",
                "--title", title,
                "--body", body,
                "--label", STALE_ISSUE_LABEL,
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if create_result.returncode == 0:
            # Parse issue number from URL output
            url = create_result.stdout.strip()
            issue_num = int(url.rstrip("/").split("/")[-1])
            logger.info("Created docs-stale issue", issue=issue_num)
            return issue_num
    except (subprocess.TimeoutExpired, FileNotFoundError, ValueError):
        pass

    logger.warning("Failed to create docs-stale issue")
    return None


def close_stale_issue() -> bool:
    """Close the open docs-stale issue after successful regeneration (FR-013).

    Returns True if an issue was found and closed.
    """
    existing = find_open_stale_issue()
    if not existing:
        return False

    try:
        result = subprocess.run(
            [
                "gh", "issue", "close", str(existing),
                "--comment", "Resolved — docs regenerated via `docs:update`.",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            logger.info("Closed docs-stale issue", issue=existing)
            return True
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    logger.warning("Failed to close docs-stale issue", issue=existing)
    return False
