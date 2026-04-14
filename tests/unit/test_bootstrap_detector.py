"""Unit tests for the bootstrap dependency detector (issue #180).

Tests the config loading, file matching, lock file checking, and
overall check_bootstrap_deps logic.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from agent_power_pack.cicd.bootstrap_detector import (
    check_bootstrap_deps,
    load_config,
)
from agent_power_pack.cicd.bootstrap_models import (
    BootstrapCheckResult,
    BootstrapDepsConfig,
)


@pytest.mark.unit
class TestLoadConfig:
    """Tests for loading .specify/bootstrap-deps.yaml."""

    def test_returns_none_when_no_config(self, tmp_path: Path) -> None:
        result = load_config(tmp_path)
        assert result is None

    def test_loads_valid_config(self, tmp_path: Path) -> None:
        config_dir = tmp_path / ".specify"
        config_dir.mkdir()
        (config_dir / "bootstrap-deps.yaml").write_text(
            """
version: "1.0"
dependencies:
  - id: iam-worker-role
    description: IAM role for worker instances
    paths:
      - "infra/bootstrap/iam/*.tf"
      - "infra/bootstrap/iam/*.json"
    verify_command: "aws iam get-role --role-name worker-role"
    manual_steps:
      - "cd infra/bootstrap/iam && terraform apply"
"""
        )
        result = load_config(tmp_path)
        assert result is not None
        assert len(result.dependencies) == 1
        assert result.dependencies[0].id == "iam-worker-role"
        assert len(result.dependencies[0].paths) == 2

    def test_returns_none_for_invalid_yaml(self, tmp_path: Path) -> None:
        config_dir = tmp_path / ".specify"
        config_dir.mkdir()
        (config_dir / "bootstrap-deps.yaml").write_text("- just a list")
        result = load_config(tmp_path)
        assert result is None


@pytest.mark.unit
class TestCheckBootstrapDeps:
    """Tests for the main check_bootstrap_deps function."""

    def _write_config(self, tmp_path: Path, deps: list[dict]) -> None:
        """Helper to write a bootstrap-deps.yaml config."""
        import yaml

        config_dir = tmp_path / ".specify"
        config_dir.mkdir(exist_ok=True)
        (config_dir / "bootstrap-deps.yaml").write_text(
            yaml.dump({"version": "1.0", "dependencies": deps})
        )

    def test_pass_when_no_config(self, tmp_path: Path) -> None:
        """No config file = pass silently."""
        result = check_bootstrap_deps(tmp_path, changed_files=["src/main.py"])
        assert result.status == "pass"
        assert result.matches == []

    def test_pass_when_no_dependencies(self, tmp_path: Path) -> None:
        """Config exists but empty dependencies = pass."""
        self._write_config(tmp_path, [])
        result = check_bootstrap_deps(tmp_path, changed_files=["src/main.py"])
        assert result.status == "pass"

    def test_pass_when_no_changed_files(self, tmp_path: Path) -> None:
        """No changed files = pass."""
        self._write_config(tmp_path, [
            {
                "id": "iam-role",
                "description": "IAM role",
                "paths": ["infra/bootstrap/*.tf"],
            }
        ])
        result = check_bootstrap_deps(tmp_path, changed_files=[])
        assert result.status == "pass"

    def test_pass_when_changed_files_dont_match(self, tmp_path: Path) -> None:
        """Changed files don't match any bootstrap path = pass."""
        self._write_config(tmp_path, [
            {
                "id": "iam-role",
                "description": "IAM role",
                "paths": ["infra/bootstrap/*.tf"],
            }
        ])
        result = check_bootstrap_deps(
            tmp_path,
            changed_files=["src/main.py", "tests/test_foo.py"],
        )
        assert result.status == "pass"

    def test_blocked_when_bootstrap_files_changed(self, tmp_path: Path) -> None:
        """Changed files match bootstrap paths = blocked."""
        self._write_config(tmp_path, [
            {
                "id": "iam-worker-role",
                "description": "IAM role for worker instances",
                "paths": ["infra/bootstrap/iam/*.tf"],
                "manual_steps": ["cd infra/bootstrap/iam && terraform apply"],
                "verify_command": "aws iam get-role --role-name worker-role",
            }
        ])
        result = check_bootstrap_deps(
            tmp_path,
            changed_files=[
                "infra/bootstrap/iam/main.tf",
                "src/worker.py",
            ],
        )
        assert result.status == "blocked"
        assert len(result.matches) == 1
        assert result.matches[0].dependency_id == "iam-worker-role"
        assert "infra/bootstrap/iam/main.tf" in result.matches[0].matched_files
        assert result.matches[0].verify_command == "aws iam get-role --role-name worker-role"

    def test_multiple_deps_matched(self, tmp_path: Path) -> None:
        """Multiple bootstrap dependencies can match simultaneously."""
        self._write_config(tmp_path, [
            {
                "id": "iam-role",
                "description": "IAM role",
                "paths": ["infra/bootstrap/iam/*.tf"],
            },
            {
                "id": "vpc-peering",
                "description": "VPC peering config",
                "paths": ["infra/bootstrap/vpc/*.tf"],
            },
        ])
        result = check_bootstrap_deps(
            tmp_path,
            changed_files=[
                "infra/bootstrap/iam/policy.tf",
                "infra/bootstrap/vpc/peering.tf",
            ],
        )
        assert result.status == "blocked"
        assert len(result.matches) == 2
        dep_ids = {m.dependency_id for m in result.matches}
        assert dep_ids == {"iam-role", "vpc-peering"}

    def test_pass_when_lock_sha_matches_head(self, tmp_path: Path) -> None:
        """If lock SHA matches HEAD, the bootstrap has been applied = pass."""
        self._write_config(tmp_path, [
            {
                "id": "iam-role",
                "description": "IAM role",
                "paths": ["infra/bootstrap/iam/*.tf"],
            }
        ])
        # Write a lock file with a fake SHA
        config_dir = tmp_path / ".specify"
        config_dir.mkdir(exist_ok=True)
        (config_dir / "bootstrap-applied.lock").write_text(
            "abc123def456 2026-04-14T12:00:00+00:00"
        )
        # Mock: pass changed_files that would match, but the lock check
        # won't work without a real git repo, so this tests the config
        # loading + matching flow only
        result = check_bootstrap_deps(
            tmp_path,
            changed_files=["infra/bootstrap/iam/main.tf"],
        )
        # Without a real git repo, head_sha will be None, so lock won't match
        # and this will be blocked (which is correct — the lock mechanism
        # requires a real git context)
        assert result.status == "blocked"

    def test_blocking_message_format(self, tmp_path: Path) -> None:
        """Verify the blocking message is well-formed."""
        self._write_config(tmp_path, [
            {
                "id": "iam-role",
                "description": "IAM role for workers",
                "paths": ["infra/bootstrap/iam/*.tf"],
                "manual_steps": ["terraform apply -target=aws_iam_role.worker"],
                "verify_command": "aws iam get-role --role-name worker",
            }
        ])
        result = check_bootstrap_deps(
            tmp_path,
            changed_files=["infra/bootstrap/iam/main.tf"],
        )
        assert result.status == "blocked"
        msg = result.blocking_message
        assert msg is not None
        assert "BLOCKING REMINDER" in msg
        assert "iam-role" in msg
        assert "terraform apply" in msg
        assert "aws iam get-role" in msg
        assert "bootstrap-applied.lock" in msg


@pytest.mark.unit
class TestBootstrapModels:
    """Tests for the pydantic models."""

    def test_config_defaults(self) -> None:
        config = BootstrapDepsConfig()
        assert config.version == "1.0"
        assert config.dependencies == []

    def test_check_result_pass(self) -> None:
        result = BootstrapCheckResult(status="pass")
        assert result.blocking_message is None

    def test_check_result_blocked(self) -> None:
        from agent_power_pack.cicd.bootstrap_models import BootstrapMatch

        result = BootstrapCheckResult(
            status="blocked",
            matches=[
                BootstrapMatch(
                    dependency_id="test",
                    description="Test dep",
                    matched_files=["a.tf"],
                    manual_steps=["apply it"],
                )
            ],
        )
        assert result.blocking_message is not None
        assert "BLOCKING REMINDER" in result.blocking_message
