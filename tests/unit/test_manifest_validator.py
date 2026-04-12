"""Unit tests for the manifest validator (T015).

Covers: valid manifest, partial-runtime rejection, vendored SHA mismatch,
illegal family, illegal mcp_tools.server — exercises every validation branch.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError as PydanticValidationError

from agent_power_pack.manifest.schema import (
    Attribution,
    McpToolRef,
    Runtime,
    SkillManifest,
)
from agent_power_pack.manifest.validator import validate_manifest


def _base_manifest(**overrides) -> SkillManifest:
    """Build a valid manifest with optional field overrides."""
    defaults = dict(
        name="test-skill",
        family="flow",
        description="A test skill.",
        triggers=["/flow:test"],
        runtimes=list(Runtime),
        prompt="Do the thing.",
        mcp_tools=[],
        attribution=None,
        order=10,
    )
    defaults.update(overrides)
    return SkillManifest(**defaults)


# --- Happy path ---


class TestValidManifest:
    def test_valid_manifest_passes(self):
        m = _base_manifest()
        result = validate_manifest(m)
        assert result.ok
        assert result.errors == []

    def test_valid_manifest_with_mcp_tools(self):
        m = _base_manifest(
            mcp_tools=[
                McpToolRef(server="plane", tool="list_issues"),
                McpToolRef(server="woodpecker", tool="get_pipeline"),
            ],
        )
        result = validate_manifest(m)
        assert result.ok


# --- Principle I: full runtime coverage ---


class TestRuntimeCoverage:
    def test_rejects_partial_runtime_coverage(self):
        m = _base_manifest(runtimes=[Runtime.CLAUDE_CODE, Runtime.CODEX_CLI])
        result = validate_manifest(m)
        assert not result.ok
        assert any("principle_i.full_runtime_coverage" in e.rule for e in result.errors)

    def test_rejects_single_runtime(self):
        m = _base_manifest(runtimes=[Runtime.CLAUDE_CODE])
        result = validate_manifest(m)
        assert not result.ok

    def test_rejects_empty_runtimes(self):
        m = _base_manifest(runtimes=[])
        result = validate_manifest(m)
        assert not result.ok
        assert any("principle_i.full_runtime_coverage" in e.rule for e in result.errors)

    def test_rejects_duplicate_runtimes(self):
        m = _base_manifest(
            runtimes=[Runtime.CLAUDE_CODE, Runtime.CODEX_CLI, Runtime.GEMINI_CLI, Runtime.CURSOR, Runtime.CLAUDE_CODE],
        )
        result = validate_manifest(m)
        assert not result.ok
        assert any("no_duplicate_runtimes" in e.rule for e in result.errors)


# --- Vendored manifest SHA cross-check ---


class TestVendoredAttribution:
    def test_sha_match_passes(self, tmp_path: Path):
        sha = "a" * 40
        vendor_dir = tmp_path / "vendor" / "skills"
        version_file = vendor_dir / "test-skill" / "VERSION"
        version_file.parent.mkdir(parents=True)
        version_file.write_text(sha)

        m = _base_manifest(
            attribution=Attribution(
                source="https://github.com/example/skills/tree/main/test-skill",
                commit_sha=sha,
                license="MIT",
                author="Test Author",
            ),
        )
        result = validate_manifest(m, vendor_dir=vendor_dir)
        assert result.ok

    def test_sha_mismatch_fails(self, tmp_path: Path):
        vendor_dir = tmp_path / "vendor" / "skills"
        version_file = vendor_dir / "test-skill" / "VERSION"
        version_file.parent.mkdir(parents=True)
        version_file.write_text("b" * 40)

        m = _base_manifest(
            attribution=Attribution(
                source="https://github.com/example/skills/tree/main/test-skill",
                commit_sha="a" * 40,
                license="MIT",
            ),
        )
        result = validate_manifest(m, vendor_dir=vendor_dir)
        assert not result.ok
        assert any("vendored.sha_mismatch" in e.rule for e in result.errors)

    def test_version_file_missing_fails(self, tmp_path: Path):
        vendor_dir = tmp_path / "vendor" / "skills"
        vendor_dir.mkdir(parents=True)

        m = _base_manifest(
            attribution=Attribution(
                source="https://github.com/example/skills/tree/main/test-skill",
                commit_sha="a" * 40,
                license="MIT",
            ),
        )
        result = validate_manifest(m, vendor_dir=vendor_dir)
        assert not result.ok
        assert any("vendored.version_file_missing" in e.rule for e in result.errors)

    def test_attribution_without_vendor_dir_skips_check(self):
        m = _base_manifest(
            attribution=Attribution(
                source="https://github.com/example/skills/tree/main/test-skill",
                commit_sha="a" * 40,
                license="MIT",
            ),
        )
        result = validate_manifest(m, vendor_dir=None)
        assert result.ok


# --- Pydantic-level validation (family, MCP server, name) ---


class TestSchemaValidation:
    def test_illegal_family_rejected_at_parse(self):
        with pytest.raises(PydanticValidationError, match="Unknown family"):
            _base_manifest(family="bogus")

    def test_illegal_mcp_server_rejected_at_parse(self):
        with pytest.raises(PydanticValidationError, match="Unknown MCP server"):
            _base_manifest(mcp_tools=[McpToolRef(server="nonexistent", tool="foo")])

    def test_illegal_name_rejected_at_parse(self):
        with pytest.raises(PydanticValidationError, match="name must match"):
            _base_manifest(name="Invalid-NAME")

    def test_name_starting_with_digit_rejected(self):
        with pytest.raises(PydanticValidationError, match="name must match"):
            _base_manifest(name="1bad")

    def test_bad_sha_format_rejected(self):
        with pytest.raises(PydanticValidationError, match="40-character hex"):
            Attribution(
                source="https://example.com",
                commit_sha="tooshort",
                license="MIT",
            )
