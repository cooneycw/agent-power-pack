"""Unit tests for docs/staleness.py (spec 002, FR-011/012/013/014)."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from ruamel.yaml import YAML

from agent_power_pack.docs.staleness import (
    StaleArtifact,
    StalenessResult,
    _build_comment_body,
    _build_issue_body,
    _signal_matches_file,
    close_stale_issue,
    create_or_update_stale_issue,
    detect_stale_artifacts,
    format_staleness_report,
)


def _write_plan(path: Path, artifacts: list[dict], project: str = "test") -> None:
    yaml = YAML()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        yaml.dump({
            "project": project,
            "convention": "docs/wiki-structure.yaml",
            "artifacts": artifacts,
        }, f)


def _init_git_repo(tmp_path: Path) -> str:
    """Initialize a git repo with one commit and return the SHA."""
    env = {
        "GIT_AUTHOR_NAME": "Test",
        "GIT_AUTHOR_EMAIL": "t@t",
        "GIT_COMMITTER_NAME": "Test",
        "GIT_COMMITTER_EMAIL": "t@t",
        "HOME": str(tmp_path),
        "PATH": "/usr/bin:/bin",
    }
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True, env=env)
    subprocess.run(
        ["git", "commit", "--allow-empty", "-m", "init"],
        cwd=tmp_path, capture_output=True, env=env,
    )
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=tmp_path, capture_output=True, text=True, env=env,
    )
    return result.stdout.strip()


# --- _signal_matches_file ---

@pytest.mark.unit
class TestSignalMatchesFile:
    def test_exact_match(self) -> None:
        assert _signal_matches_file("README.md", "README.md")

    def test_directory_match(self) -> None:
        assert _signal_matches_file("src/", "src/foo/bar.py")

    def test_directory_without_slash(self) -> None:
        assert _signal_matches_file("src", "src/foo/bar.py")

    def test_no_match(self) -> None:
        assert not _signal_matches_file("README.md", "CHANGELOG.md")

    def test_partial_name_no_match(self) -> None:
        assert not _signal_matches_file("src/foo", "src/foobar/baz.py")

    def test_directory_match_deep(self) -> None:
        assert _signal_matches_file("manifests/", "manifests/docs/update.yaml")


# --- detect_stale_artifacts ---

@pytest.mark.unit
class TestDetectStaleArtifacts:
    def test_no_plan_skipped(self, tmp_path: Path) -> None:
        """AC: No checks occur without docs/plan.yaml (FR-014)."""
        result = detect_stale_artifacts(tmp_path / "docs" / "plan.yaml", tmp_path)
        assert result.skipped
        assert "skipped" in result.reason

    def test_null_sha_always_stale(self, tmp_path: Path) -> None:
        """Artifact with last_commit_sha: null is always stale."""
        plan_path = tmp_path / "docs" / "plan.yaml"
        _write_plan(plan_path, [
            {
                "type": "prose_docs",
                "name": "Guide",
                "last_commit_sha": None,
                "source_signals": ["README.md"],
            },
        ])
        _init_git_repo(tmp_path)

        result = detect_stale_artifacts(plan_path, tmp_path)
        assert result.has_stale
        assert len(result.stale) == 1
        assert result.stale[0].artifact_type == "prose_docs"
        assert result.stale[0].last_commit_sha is None

    def test_current_sha_not_stale(self, tmp_path: Path) -> None:
        """Artifact at current SHA is not stale."""
        sha = _init_git_repo(tmp_path)
        plan_path = tmp_path / "docs" / "plan.yaml"
        _write_plan(plan_path, [
            {
                "type": "prose_docs",
                "name": "Guide",
                "last_commit_sha": sha,
                "source_signals": ["README.md"],
            },
        ])

        result = detect_stale_artifacts(plan_path, tmp_path)
        assert not result.has_stale
        assert "prose_docs" in result.current

    def test_stale_when_source_files_changed(self, tmp_path: Path) -> None:
        """AC: Stale artifacts correctly identified when source files changed."""
        env = {
            "GIT_AUTHOR_NAME": "Test",
            "GIT_AUTHOR_EMAIL": "t@t",
            "GIT_COMMITTER_NAME": "Test",
            "GIT_COMMITTER_EMAIL": "t@t",
            "HOME": str(tmp_path),
            "PATH": "/usr/bin:/bin",
        }

        # Create repo with initial commit
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True, env=env)
        (tmp_path / "README.md").write_text("# Initial")
        subprocess.run(["git", "add", "README.md"], cwd=tmp_path, capture_output=True, env=env)
        subprocess.run(
            ["git", "commit", "-m", "init"],
            cwd=tmp_path, capture_output=True, env=env,
        )
        old_sha = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=tmp_path, capture_output=True, text=True, env=env,
        ).stdout.strip()

        # Create plan referencing README.md
        plan_path = tmp_path / "docs" / "plan.yaml"
        _write_plan(plan_path, [
            {
                "type": "prose_docs",
                "name": "Guide",
                "last_commit_sha": old_sha,
                "source_signals": ["README.md"],
            },
        ])

        # Make a change to README.md and commit
        (tmp_path / "README.md").write_text("# Updated")
        subprocess.run(["git", "add", "README.md"], cwd=tmp_path, capture_output=True, env=env)
        subprocess.run(
            ["git", "commit", "-m", "update readme"],
            cwd=tmp_path, capture_output=True, env=env,
        )

        result = detect_stale_artifacts(plan_path, tmp_path)
        assert result.has_stale
        assert result.stale[0].artifact_type == "prose_docs"
        assert "README.md" in result.stale[0].changed_files

    def test_not_stale_when_unrelated_files_changed(self, tmp_path: Path) -> None:
        """Artifact not stale when changed files don't match source_signals."""
        env = {
            "GIT_AUTHOR_NAME": "Test",
            "GIT_AUTHOR_EMAIL": "t@t",
            "GIT_COMMITTER_NAME": "Test",
            "GIT_COMMITTER_EMAIL": "t@t",
            "HOME": str(tmp_path),
            "PATH": "/usr/bin:/bin",
        }

        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True, env=env)
        (tmp_path / "README.md").write_text("# Initial")
        (tmp_path / "unrelated.txt").write_text("foo")
        subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True, env=env)
        subprocess.run(
            ["git", "commit", "-m", "init"],
            cwd=tmp_path, capture_output=True, env=env,
        )
        old_sha = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=tmp_path, capture_output=True, text=True, env=env,
        ).stdout.strip()

        plan_path = tmp_path / "docs" / "plan.yaml"
        _write_plan(plan_path, [
            {
                "type": "prose_docs",
                "name": "Guide",
                "last_commit_sha": old_sha,
                "source_signals": ["README.md"],
            },
        ])

        # Change an unrelated file
        (tmp_path / "unrelated.txt").write_text("bar")
        subprocess.run(["git", "add", "unrelated.txt"], cwd=tmp_path, capture_output=True, env=env)
        subprocess.run(
            ["git", "commit", "-m", "update unrelated"],
            cwd=tmp_path, capture_output=True, env=env,
        )

        result = detect_stale_artifacts(plan_path, tmp_path)
        assert not result.has_stale

    def test_empty_artifacts(self, tmp_path: Path) -> None:
        plan_path = tmp_path / "docs" / "plan.yaml"
        _write_plan(plan_path, [])
        result = detect_stale_artifacts(plan_path, tmp_path)
        assert not result.has_stale
        assert "No artifacts" in result.reason


# --- format_staleness_report ---

@pytest.mark.unit
class TestFormatStalenessReport:
    def test_skipped_report(self, tmp_path: Path) -> None:
        result = StalenessResult(skipped=True, reason="No docs/plan.yaml")
        report = format_staleness_report(result, tmp_path)
        assert "No docs/plan.yaml" in report

    def test_clean_report(self, tmp_path: Path) -> None:
        result = StalenessResult(current=["prose_docs", "api_reference"])
        report = format_staleness_report(result, tmp_path)
        assert "up to date" in report

    def test_stale_report(self, tmp_path: Path) -> None:
        result = StalenessResult(
            stale=[
                StaleArtifact(
                    artifact_type="prose_docs",
                    name="Guide",
                    last_commit_sha="abc123",
                    changed_files=["README.md"],
                    source_signals=["README.md"],
                ),
            ],
            current=["api_reference"],
        )
        report = format_staleness_report(result, tmp_path)
        assert "1 stale" in report
        assert "Guide" in report
        assert "README.md" in report
        assert "docs update" in report


# --- Issue lifecycle (FR-013) ---

@pytest.mark.unit
class TestIssueLifecycle:
    def test_create_new_issue(self) -> None:
        """AC: New issue created when no open docs-stale issue exists."""
        result = StalenessResult(
            stale=[StaleArtifact("prose_docs", "Guide", "abc", ["README.md"], ["README.md"])],
        )

        with patch("agent_power_pack.docs.staleness.find_open_stale_issue", return_value=None), \
             patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="https://github.com/org/repo/issues/42\n",
            )
            issue_num = create_or_update_stale_issue(result)
            assert issue_num == 42

    def test_comment_on_existing_issue(self) -> None:
        """AC: Comment added to existing open issue (no duplicates)."""
        result = StalenessResult(
            stale=[StaleArtifact("prose_docs", "Guide", "abc", ["README.md"], ["README.md"])],
        )

        with patch("agent_power_pack.docs.staleness.find_open_stale_issue", return_value=99), \
             patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="")
            issue_num = create_or_update_stale_issue(result)
            assert issue_num == 99
            # Verify gh issue comment was called, not gh issue create
            call_args = mock_run.call_args[0][0]
            assert "comment" in call_args

    def test_close_stale_issue(self) -> None:
        """AC: Issue closed after successful docs:update."""
        with patch("agent_power_pack.docs.staleness.find_open_stale_issue", return_value=99), \
             patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="")
            closed = close_stale_issue()
            assert closed
            call_args = mock_run.call_args[0][0]
            assert "close" in call_args

    def test_close_no_open_issue(self) -> None:
        with patch("agent_power_pack.docs.staleness.find_open_stale_issue", return_value=None):
            closed = close_stale_issue()
            assert not closed

    def test_no_issue_when_not_stale(self) -> None:
        result = StalenessResult(current=["prose_docs"])
        issue_num = create_or_update_stale_issue(result)
        assert issue_num is None


# --- _build_issue_body ---

@pytest.mark.unit
class TestBuildIssueBody:
    def test_body_contains_artifacts(self) -> None:
        result = StalenessResult(
            stale=[
                StaleArtifact("prose_docs", "Guide", "abc123", ["README.md"], ["README.md"]),
                StaleArtifact("api_reference", "API", None, ["(never generated)"], ["src/"]),
            ],
        )
        body = _build_issue_body(result)
        assert "Guide" in body
        assert "API" in body
        assert "agent-power-pack docs update" in body

    def test_comment_body(self) -> None:
        result = StalenessResult(
            stale=[StaleArtifact("prose_docs", "Guide", "abc", ["a.py", "b.py"], ["src/"])],
        )
        comment = _build_comment_body(result)
        assert "Guide" in comment
        assert "2 file(s)" in comment
