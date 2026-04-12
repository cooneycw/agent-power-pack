"""Unit tests for the YAML manifest loader (T016).

Covers: round-trip fidelity (comments preserved, field order stable),
loading from file and string, loading all manifests from a directory.
"""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest

from agent_power_pack.manifest.loader import (
    dump_raw_yaml,
    load_all_manifests,
    load_manifest,
    load_manifest_from_string,
    load_raw_yaml,
)
from agent_power_pack.manifest.schema import Runtime


SAMPLE_YAML = dedent("""\
    # This is a comment that should survive round-trips
    name: test-skill
    family: flow
    description: A test skill for round-trip testing.
    triggers:
      - /flow:test
      - flow test
    runtimes:
      - claude-code
      - codex-cli
      - gemini-cli
      - cursor
    prompt: |
      Do the thing.
    mcp_tools: []
    attribution: null
    order: 10
""")


class TestLoadManifestFromString:
    def test_loads_valid_yaml(self):
        m = load_manifest_from_string(SAMPLE_YAML)
        assert m.name == "test-skill"
        assert m.family == "flow"
        assert m.runtimes == list(Runtime)
        assert m.order == 10

    def test_triggers_preserved(self):
        m = load_manifest_from_string(SAMPLE_YAML)
        assert len(m.triggers) == 2
        assert "/flow:test" in m.triggers

    def test_invalid_yaml_raises(self):
        from pydantic import ValidationError

        bad = SAMPLE_YAML.replace("family: flow", "family: bogus")
        with pytest.raises(ValidationError, match="Unknown family"):
            load_manifest_from_string(bad)


class TestLoadManifestFromFile:
    def test_loads_from_path(self, tmp_path: Path):
        p = tmp_path / "test.yaml"
        p.write_text(SAMPLE_YAML)
        m = load_manifest(p)
        assert m.name == "test-skill"

    def test_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            load_manifest(Path("/nonexistent/path.yaml"))


class TestRoundTripFidelity:
    def test_comments_preserved(self, tmp_path: Path):
        src = tmp_path / "src.yaml"
        dst = tmp_path / "dst.yaml"
        src.write_text(SAMPLE_YAML)

        data = load_raw_yaml(src)
        dump_raw_yaml(data, dst)

        output = dst.read_text()
        assert "# This is a comment that should survive round-trips" in output

    def test_field_order_stable(self, tmp_path: Path):
        src = tmp_path / "src.yaml"
        dst = tmp_path / "dst.yaml"
        src.write_text(SAMPLE_YAML)

        data = load_raw_yaml(src)
        dump_raw_yaml(data, dst)

        output = dst.read_text()
        lines = [line.split(":")[0].strip() for line in output.splitlines() if ":" in line and not line.startswith("#") and not line.startswith(" ")]
        # name should come before family, family before description, etc.
        expected_order = ["name", "family", "description", "triggers", "runtimes", "prompt", "mcp_tools", "attribution", "order"]
        actual_order = [k for k in lines if k in expected_order]
        assert actual_order == expected_order


class TestLoadAllManifests:
    def test_loads_multiple_manifests(self, tmp_path: Path):
        flow_dir = tmp_path / "flow"
        flow_dir.mkdir()
        for name in ["alpha", "beta"]:
            yaml_text = SAMPLE_YAML.replace("name: test-skill", f"name: {name}").replace("order: 10", f"order: {10 if name == 'alpha' else 20}")
            (flow_dir / f"{name}.yaml").write_text(yaml_text)

        manifests = load_all_manifests(tmp_path)
        assert len(manifests) == 2
        assert manifests[0].name == "alpha"
        assert manifests[1].name == "beta"

    def test_sorted_by_family_order_name(self, tmp_path: Path):
        for family in ["flow", "grill"]:
            d = tmp_path / family
            d.mkdir()
            yaml_text = SAMPLE_YAML.replace("name: test-skill", f"name: skill-{family}").replace("family: flow", f"family: {family}")
            (d / f"skill-{family}.yaml").write_text(yaml_text)

        manifests = load_all_manifests(tmp_path)
        assert manifests[0].family == "flow"
        assert manifests[1].family == "grill"

    def test_empty_dir_returns_empty_list(self, tmp_path: Path):
        manifests = load_all_manifests(tmp_path)
        assert manifests == []
