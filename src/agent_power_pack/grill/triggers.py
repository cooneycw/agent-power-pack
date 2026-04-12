"""should_grill() trigger evaluator (T065).

Parses git diff --numstat output and decides whether grill-yourself should fire
based on configured thresholds and optional commit trailer overrides.
"""

from __future__ import annotations

import fnmatch

from pydantic import BaseModel

from agent_power_pack.grill.config import GrillTriggerConfig, load_grill_config
from agent_power_pack.logging import get_logger

log = get_logger("grill.triggers")


class GrillDecision(BaseModel):
    """Result of evaluating whether grill-yourself should fire."""

    should_fire: bool
    reason: str
    lines_changed: int
    files_changed: int


def _parse_numstat(numstat: str) -> list[tuple[int, int, str]]:
    """Parse git diff --numstat output into (added, deleted, filepath) tuples.

    Binary files show '-' for added/deleted — treated as 0.
    """
    entries: list[tuple[int, int, str]] = []
    for line in numstat.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split("\t", 2)
        if len(parts) < 3:
            continue
        added_str, deleted_str, filepath = parts
        added = int(added_str) if added_str != "-" else 0
        deleted = int(deleted_str) if deleted_str != "-" else 0
        entries.append((added, deleted, filepath))
    return entries


def _is_excluded(filepath: str, exclude_globs: list[str]) -> bool:
    """Check if a filepath matches any of the exclude globs."""
    return any(fnmatch.fnmatch(filepath, glob) for glob in exclude_globs)


def should_grill(
    numstat: str,
    config: GrillTriggerConfig | None = None,
    trailer: str | None = None,
) -> GrillDecision:
    """Evaluate whether grill-yourself should fire for the given diff.

    Args:
        numstat: Raw output of ``git diff --numstat``.
        config: Trigger config; loaded from disk if *None*.
        trailer: Optional trailer value from HEAD commit message
                 (``"force"``, ``"skip"``, or *None*).

    Returns:
        A :class:`GrillDecision` with the verdict and supporting data.
    """
    if config is None:
        config = load_grill_config()

    entries = _parse_numstat(numstat)

    # Filter out excluded files
    filtered = [
        (added, deleted, fp)
        for added, deleted, fp in entries
        if not _is_excluded(fp, config.exclude_globs)
    ]

    total_lines = sum(added + deleted for added, deleted, _ in filtered)
    file_count = len(filtered)

    # Trailer overrides
    if trailer == "force":
        log.info("grill forced via trailer", lines=total_lines, files=file_count)
        return GrillDecision(
            should_fire=True,
            reason="Forced via grill-yourself: force trailer",
            lines_changed=total_lines,
            files_changed=file_count,
        )
    if trailer == "skip":
        log.info("grill skipped via trailer", lines=total_lines, files=file_count)
        return GrillDecision(
            should_fire=False,
            reason="Skipped via grill-yourself: skip trailer",
            lines_changed=total_lines,
            files_changed=file_count,
        )

    # Threshold checks — "exceeds" means strictly greater than
    if total_lines > config.max_lines:
        reason = (
            f"Lines changed ({total_lines}) exceeds threshold ({config.max_lines})"
        )
        log.info("grill triggered by lines", lines=total_lines, threshold=config.max_lines)
        return GrillDecision(
            should_fire=True,
            reason=reason,
            lines_changed=total_lines,
            files_changed=file_count,
        )

    if file_count > config.max_files:
        reason = (
            f"Files changed ({file_count}) exceeds threshold ({config.max_files})"
        )
        log.info("grill triggered by files", files=file_count, threshold=config.max_files)
        return GrillDecision(
            should_fire=True,
            reason=reason,
            lines_changed=total_lines,
            files_changed=file_count,
        )

    log.debug(
        "grill not triggered",
        lines=total_lines,
        files=file_count,
        max_lines=config.max_lines,
        max_files=config.max_files,
    )
    return GrillDecision(
        should_fire=False,
        reason=(
            f"Below thresholds (lines={total_lines}/{config.max_lines}, "
            f"files={file_count}/{config.max_files})"
        ),
        lines_changed=total_lines,
        files_changed=file_count,
    )
