"""Unit tests for vendored skill validation (T078).

Covers:
  1. SHA mismatch detection — VERSION file SHA vs manifest attribution.commit_sha
  2. License-match validation — ATTRIBUTION.md contains correct SHA for vendored skills
"""

from __future__ import annotations

from pathlib import Path

import pytest

from agent_power_pack.manifest.schema import (
    Attribution,
    Runtime,
    SkillManifest,
)
from agent_power_pack.manifest.validator import validate_manifest


def _grill_me_manifest(commit_sha: str = "a" * 40) -> SkillManifest:
    """Build a grill:me manifest with the given attribution SHA."""
    return SkillManifest(
        name="me",
        family="grill",
        description="Interrogation skill (vendored from mattpocock/skills).",
        triggers=["/grill:me", "grill me"],
        runtimes=list(Runtime),
        prompt="Interview me relentlessly.",
        mcp_tools=[],
        attribution=Attribution(
            source="https://github.com/mattpocock/skills/tree/main/grill-me",
            commit_sha=commit_sha,
            license="MIT",
            author="Matt Pocock",
        ),
        order=10,
    )


class TestSHAMismatchDetection:
    """Verify that the validator catches SHA drift between VERSION and manifest."""

    def test_matching_sha_passes(self, tmp_path: Path):
        sha = "a" * 40
        vendor_dir = tmp_path / "vendor" / "skills"
        version_file = vendor_dir / "me" / "VERSION"
        version_file.parent.mkdir(parents=True)
        version_file.write_text(sha + "\n")

        manifest = _grill_me_manifest(commit_sha=sha)
        result = validate_manifest(manifest, vendor_dir=vendor_dir)
        assert result.ok, f"Expected pass, got errors: {result.errors}"

    def test_mismatched_sha_fails(self, tmp_path: Path):
        vendor_dir = tmp_path / "vendor" / "skills"
        version_file = vendor_dir / "me" / "VERSION"
        version_file.parent.mkdir(parents=True)
        version_file.write_text("b" * 40 + "\n")

        manifest = _grill_me_manifest(commit_sha="a" * 40)
        result = validate_manifest(manifest, vendor_dir=vendor_dir)
        assert not result.ok
        assert any("vendored.sha_mismatch" in e.rule for e in result.errors)

    def test_missing_version_file_fails(self, tmp_path: Path):
        vendor_dir = tmp_path / "vendor" / "skills"
        vendor_dir.mkdir(parents=True)

        manifest = _grill_me_manifest(commit_sha="a" * 40)
        result = validate_manifest(manifest, vendor_dir=vendor_dir)
        assert not result.ok
        assert any("vendored.version_file_missing" in e.rule for e in result.errors)


class TestLicenseMatchValidation:
    """Verify ATTRIBUTION.md contains the correct SHA for each vendored skill."""

    @pytest.fixture()
    def repo_root(self) -> Path:
        """Return the repository root directory."""
        return Path(__file__).resolve().parent.parent.parent

    def test_attribution_contains_version_sha(self, repo_root: Path):
        """ATTRIBUTION.md must contain the same SHA as vendor/skills/grill-me/VERSION."""
        version_file = repo_root / "vendor" / "skills" / "grill-me" / "VERSION"
        attribution_file = repo_root / "ATTRIBUTION.md"

        assert version_file.exists(), f"VERSION file not found at {version_file}"
        assert attribution_file.exists(), f"ATTRIBUTION.md not found at {attribution_file}"

        pinned_sha = version_file.read_text().strip()
        attr_content = attribution_file.read_text()

        assert pinned_sha in attr_content, (
            f"ATTRIBUTION.md does not contain the vendored SHA {pinned_sha}"
        )

    def test_manifest_sha_matches_version_file(self, repo_root: Path):
        """manifests/grill/me.yaml attribution.commit_sha must match VERSION."""
        from ruamel.yaml import YAML

        version_file = repo_root / "vendor" / "skills" / "grill-me" / "VERSION"
        manifest_file = repo_root / "manifests" / "grill" / "me.yaml"

        assert version_file.exists()
        assert manifest_file.exists()

        pinned_sha = version_file.read_text().strip()

        yaml = YAML()
        data = yaml.load(manifest_file)
        manifest_sha = data["attribution"]["commit_sha"]

        assert manifest_sha == pinned_sha, (
            f"Manifest SHA ({manifest_sha}) does not match VERSION ({pinned_sha})"
        )

    def test_attribution_license_is_mit(self, repo_root: Path):
        """ATTRIBUTION.md must record MIT license for grill-me."""
        attribution_file = repo_root / "ATTRIBUTION.md"
        assert attribution_file.exists()

        content = attribution_file.read_text()
        # Find the grill-me row and verify it says MIT
        for line in content.splitlines():
            if "grill-me" in line and "|" in line:
                assert "MIT" in line, (
                    f"grill-me row in ATTRIBUTION.md does not mention MIT: {line}"
                )
                return

        pytest.fail("grill-me not found in ATTRIBUTION.md table")
