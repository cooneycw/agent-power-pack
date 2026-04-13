"""Issue/PR backend abstraction (T146).

Provides helpers for PR/issue side effects that gracefully degrade when
the GitHub CLI (``gh``) is not available.  All ``gh``-dependent operations
are optional adapters — ``flow finish`` never hard-fails solely because
``gh`` is missing.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from typing import Literal

from agent_power_pack.logging import get_logger

log = get_logger("issue_backend")

Backend = Literal["github", "none"]


@dataclass
class GhResult:
    """Result of an optional ``gh`` CLI call."""

    ok: bool
    stdout: str
    backend: Backend


def gh_available() -> bool:
    """Return True if the ``gh`` CLI is installed and executable."""
    try:
        result = subprocess.run(
            ["gh", "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def detect_backend() -> Backend:
    """Detect which issue backend is available.

    Returns ``"github"`` when the ``gh`` CLI is present, otherwise ``"none"``.
    """
    if gh_available():
        return "github"
    return "none"


def try_gh(args: list[str], *, timeout: int = 10) -> GhResult:
    """Run a ``gh`` CLI command, returning a result instead of raising.

    If ``gh`` is not installed or the command fails, ``GhResult.ok`` is False
    and ``GhResult.stdout`` contains an empty string.
    """
    try:
        result = subprocess.run(
            ["gh", *args],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode == 0:
            return GhResult(ok=True, stdout=result.stdout.strip(), backend="github")
        log.warning("gh command failed", args=args, stderr=result.stderr.strip())
        return GhResult(ok=False, stdout="", backend="github")
    except FileNotFoundError:
        log.info("gh CLI not found — skipping", args=args)
        return GhResult(ok=False, stdout="", backend="none")
    except subprocess.TimeoutExpired:
        log.warning("gh command timed out", args=args)
        return GhResult(ok=False, stdout="", backend="github")


def get_current_pr_number() -> str | None:
    """Return the PR number for the current branch, or None."""
    result = try_gh(["pr", "view", "--json", "number", "-q", ".number"])
    return result.stdout if result.ok and result.stdout else None


def attach_body_to_pr(body: str) -> bool:
    """Attempt to set the PR body via ``gh pr edit``.

    Returns True on success, False if ``gh`` is unavailable or the call fails.
    """
    result = try_gh(["pr", "edit", "--body", body])
    return result.ok
