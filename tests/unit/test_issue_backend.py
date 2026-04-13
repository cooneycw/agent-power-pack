"""Unit tests for issue_backend module (T146).

Covers: gh_available(), detect_backend(), try_gh(), get_current_pr_number(),
attach_body_to_pr() — all with gh mocked as present/absent.
"""

from __future__ import annotations

import subprocess
from unittest.mock import patch

import pytest

from agent_power_pack.issue_backend import (
    attach_body_to_pr,
    detect_backend,
    get_current_pr_number,
    gh_available,
    try_gh,
)


@pytest.mark.unit
class TestGhAvailable:
    """Tests for gh_available()."""

    def test_returns_true_when_gh_exists(self) -> None:
        with patch("agent_power_pack.issue_backend.subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=["gh", "--version"], returncode=0, stdout="gh version 2.50.0\n"
            )
            assert gh_available() is True

    def test_returns_false_when_gh_missing(self) -> None:
        with patch(
            "agent_power_pack.issue_backend.subprocess.run",
            side_effect=FileNotFoundError,
        ):
            assert gh_available() is False

    def test_returns_false_on_timeout(self) -> None:
        with patch(
            "agent_power_pack.issue_backend.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="gh", timeout=5),
        ):
            assert gh_available() is False


@pytest.mark.unit
class TestDetectBackend:
    """Tests for detect_backend()."""

    def test_github_when_gh_available(self) -> None:
        with patch("agent_power_pack.issue_backend.gh_available", return_value=True):
            assert detect_backend() == "github"

    def test_none_when_gh_missing(self) -> None:
        with patch("agent_power_pack.issue_backend.gh_available", return_value=False):
            assert detect_backend() == "none"


@pytest.mark.unit
class TestTryGh:
    """Tests for try_gh()."""

    def test_success(self) -> None:
        with patch("agent_power_pack.issue_backend.subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=["gh", "pr", "view"], returncode=0, stdout="42\n"
            )
            result = try_gh(["pr", "view"])
            assert result.ok is True
            assert result.stdout == "42"
            assert result.backend == "github"

    def test_failure_returncode(self) -> None:
        with patch("agent_power_pack.issue_backend.subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=["gh", "pr", "view"],
                returncode=1,
                stdout="",
                stderr="no PR found",
            )
            result = try_gh(["pr", "view"])
            assert result.ok is False
            assert result.backend == "github"

    def test_file_not_found(self) -> None:
        with patch(
            "agent_power_pack.issue_backend.subprocess.run",
            side_effect=FileNotFoundError,
        ):
            result = try_gh(["pr", "view"])
            assert result.ok is False
            assert result.backend == "none"

    def test_timeout(self) -> None:
        with patch(
            "agent_power_pack.issue_backend.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="gh", timeout=10),
        ):
            result = try_gh(["pr", "view"])
            assert result.ok is False
            assert result.backend == "github"


@pytest.mark.unit
class TestGetCurrentPrNumber:
    """Tests for get_current_pr_number()."""

    def test_returns_number_when_pr_exists(self) -> None:
        with patch("agent_power_pack.issue_backend.try_gh") as mock_try:
            from agent_power_pack.issue_backend import GhResult

            mock_try.return_value = GhResult(ok=True, stdout="42", backend="github")
            assert get_current_pr_number() == "42"

    def test_returns_none_when_no_pr(self) -> None:
        with patch("agent_power_pack.issue_backend.try_gh") as mock_try:
            from agent_power_pack.issue_backend import GhResult

            mock_try.return_value = GhResult(ok=False, stdout="", backend="none")
            assert get_current_pr_number() is None

    def test_returns_none_when_empty_stdout(self) -> None:
        with patch("agent_power_pack.issue_backend.try_gh") as mock_try:
            from agent_power_pack.issue_backend import GhResult

            mock_try.return_value = GhResult(ok=True, stdout="", backend="github")
            assert get_current_pr_number() is None


@pytest.mark.unit
class TestAttachBodyToPr:
    """Tests for attach_body_to_pr()."""

    def test_returns_true_on_success(self) -> None:
        with patch("agent_power_pack.issue_backend.try_gh") as mock_try:
            from agent_power_pack.issue_backend import GhResult

            mock_try.return_value = GhResult(ok=True, stdout="", backend="github")
            assert attach_body_to_pr("some body") is True

    def test_returns_false_when_gh_missing(self) -> None:
        with patch("agent_power_pack.issue_backend.try_gh") as mock_try:
            from agent_power_pack.issue_backend import GhResult

            mock_try.return_value = GhResult(ok=False, stdout="", backend="none")
            assert attach_body_to_pr("some body") is False
