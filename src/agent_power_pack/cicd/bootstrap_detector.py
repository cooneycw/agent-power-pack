"""Bootstrap dependency detector (issue #180).

Checks whether a git diff touches admin-only bootstrap dependencies
declared in `.specify/bootstrap-deps.yaml`.  If the config file does
not exist the check passes silently — no bootstrap boundaries declared
means nothing to block.

The detector also reads `.specify/bootstrap-applied.lock` to see if
the manual apply has already been recorded for the current HEAD.
"""

from __future__ import annotations

import fnmatch
import subprocess
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML

from agent_power_pack.cicd.bootstrap_models import (
    BootstrapCheckResult,
    BootstrapDepsConfig,
    BootstrapMatch,
)
from agent_power_pack.logging import get_logger

log = get_logger("cicd.bootstrap_detector")

CONFIG_PATH = ".specify/bootstrap-deps.yaml"
LOCK_PATH = ".specify/bootstrap-applied.lock"


def load_config(repo_root: Path) -> BootstrapDepsConfig | None:
    """Load bootstrap-deps.yaml, returning None if it doesn't exist."""
    config_file = repo_root / CONFIG_PATH
    if not config_file.exists():
        return None
    yaml = YAML(typ="safe")
    data: dict[str, Any] = yaml.load(config_file)
    if not isinstance(data, dict):
        log.warning("bootstrap_config_invalid", path=str(config_file))
        return None
    return BootstrapDepsConfig.model_validate(data)


def _read_lock(repo_root: Path) -> str | None:
    """Read the commit SHA from the bootstrap-applied lock file."""
    lock_file = repo_root / LOCK_PATH
    if not lock_file.exists():
        return None
    content = lock_file.read_text().strip()
    # Format: "<sha> <timestamp>" — we only need the SHA
    parts = content.split()
    return parts[0] if parts else None


def _get_head_sha(repo_root: Path) -> str | None:
    """Get the current HEAD commit SHA."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            cwd=repo_root,
            check=False,
        )
        return result.stdout.strip() if result.returncode == 0 else None
    except FileNotFoundError:
        return None


def _get_changed_files(repo_root: Path, base: str = "origin/main") -> list[str]:
    """Get the list of files changed since the base branch."""
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", base + "...HEAD"],
            capture_output=True,
            text=True,
            cwd=repo_root,
            check=False,
        )
        if result.returncode != 0:
            # Fall back to diff against HEAD~1 if base doesn't exist
            result = subprocess.run(
                ["git", "diff", "--name-only", "HEAD~1"],
                capture_output=True,
                text=True,
                cwd=repo_root,
                check=False,
            )
        return [f.strip() for f in result.stdout.strip().splitlines() if f.strip()]
    except FileNotFoundError:
        return []


def check_bootstrap_deps(
    repo_root: Path,
    *,
    changed_files: list[str] | None = None,
    base: str = "origin/main",
) -> BootstrapCheckResult:
    """Check if the current diff touches any declared bootstrap dependencies.

    Args:
        repo_root: Path to the repository root.
        changed_files: Override the list of changed files (for testing).
        base: Base ref to diff against.

    Returns:
        BootstrapCheckResult with status "pass" or "blocked".
    """
    config = load_config(repo_root)
    if config is None or not config.dependencies:
        log.info("bootstrap_check_skip", reason="no config or no dependencies declared")
        return BootstrapCheckResult(status="pass")

    if changed_files is None:
        changed_files = _get_changed_files(repo_root, base=base)

    if not changed_files:
        return BootstrapCheckResult(status="pass")

    head_sha = _get_head_sha(repo_root)
    lock_sha = _read_lock(repo_root)

    # If the lock SHA matches HEAD, the bootstrap has been applied
    if lock_sha and head_sha and lock_sha == head_sha:
        log.info("bootstrap_check_pass", reason="lock SHA matches HEAD")
        return BootstrapCheckResult(
            status="pass",
            lock_sha=lock_sha,
            current_sha=head_sha,
        )

    # Check each dependency's paths against the changed files
    matches: list[BootstrapMatch] = []
    for dep in config.dependencies:
        matched_files: list[str] = []
        for pattern in dep.paths:
            for changed_file in changed_files:
                if fnmatch.fnmatch(changed_file, pattern):
                    matched_files.append(changed_file)
        if matched_files:
            matches.append(
                BootstrapMatch(
                    dependency_id=dep.id,
                    description=dep.description,
                    matched_files=sorted(set(matched_files)),
                    manual_steps=dep.manual_steps,
                    verify_command=dep.verify_command,
                )
            )

    if not matches:
        return BootstrapCheckResult(
            status="pass",
            lock_sha=lock_sha,
            current_sha=head_sha,
        )

    log.warning(
        "bootstrap_check_blocked",
        matched_deps=[m.dependency_id for m in matches],
        matched_files_count=sum(len(m.matched_files) for m in matches),
    )
    return BootstrapCheckResult(
        status="blocked",
        matches=matches,
        lock_sha=lock_sha,
        current_sha=head_sha,
    )
