"""Unit tests for docs/plan_generator.py (spec 002, FR-003)."""

from __future__ import annotations

from pathlib import Path

import pytest
from ruamel.yaml import YAML

from agent_power_pack.docs.plan_generator import generate_plan, write_plan_yaml
from agent_power_pack.docs.signal_detector import ArtifactProposal


def _make_proposal(
    art_type: str = "prose_docs",
    model: str = "claude",
    confidence: float = 0.8,
) -> ArtifactProposal:
    return ArtifactProposal(
        name="Test Artifact",
        type=art_type,
        model=model,
        source_signals=["README.md"],
        depth="overview",
        confidence=confidence,
    )


@pytest.mark.unit
class TestGeneratePlan:
    def test_creates_new_plan(self, tmp_path: Path) -> None:
        plan_path = tmp_path / "plan.yaml"
        proposals = [_make_proposal()]
        plan = generate_plan("myproject", proposals, plan_path)
        assert plan["project"] == "myproject"
        assert len(plan["artifacts"]) == 1
        assert plan["artifacts"][0]["type"] == "prose_docs"

    def test_preserves_existing_metadata(self, tmp_path: Path) -> None:
        plan_path = tmp_path / "plan.yaml"
        yaml = YAML()
        with open(plan_path, "w") as f:
            yaml.dump({
                "project": "existing-project",
                "convention": "custom/path.yaml",
                "artifacts": [],
            }, f)

        proposals = [_make_proposal()]
        plan = generate_plan("myproject", proposals, plan_path)
        assert plan["project"] == "existing-project"
        assert plan["convention"] == "custom/path.yaml"

    def test_merges_with_existing_artifacts(self, tmp_path: Path) -> None:
        plan_path = tmp_path / "plan.yaml"
        yaml = YAML()
        with open(plan_path, "w") as f:
            yaml.dump({
                "project": "myproject",
                "convention": "docs/wiki-structure.yaml",
                "artifacts": [
                    {
                        "name": "Custom Guide",
                        "type": "prose_docs",
                        "model": "gpt-4o",  # manual override
                        "source_signals": ["old_signal"],
                        "depth": "detailed",
                        "confidence": 0.5,
                    },
                ],
            }, f)

        proposals = [_make_proposal(confidence=0.9)]
        plan = generate_plan("myproject", proposals, plan_path)
        # Model override preserved
        assert plan["artifacts"][0]["model"] == "gpt-4o"
        # Confidence and signals updated
        assert plan["artifacts"][0]["confidence"] == 0.9
        assert plan["artifacts"][0]["source_signals"] == ["README.md"]

    def test_preserves_user_added_artifacts(self, tmp_path: Path) -> None:
        plan_path = tmp_path / "plan.yaml"
        yaml = YAML()
        with open(plan_path, "w") as f:
            yaml.dump({
                "project": "myproject",
                "convention": "docs/wiki-structure.yaml",
                "artifacts": [
                    {
                        "name": "Custom Artifact",
                        "type": "custom_runbook",
                        "model": "claude",
                        "source_signals": ["scripts/"],
                        "depth": "detailed",
                        "confidence": 1.0,
                    },
                ],
            }, f)

        proposals = [_make_proposal()]
        plan = generate_plan("myproject", proposals, plan_path)
        types = [a["type"] for a in plan["artifacts"]]
        assert "custom_runbook" in types
        assert "prose_docs" in types

    def test_empty_proposals(self, tmp_path: Path) -> None:
        plan_path = tmp_path / "plan.yaml"
        plan = generate_plan("myproject", [], plan_path)
        assert plan["artifacts"] == []


@pytest.mark.unit
class TestWritePlanYaml:
    def test_writes_valid_yaml(self, tmp_path: Path) -> None:
        plan_path = tmp_path / "plan.yaml"
        plan = {
            "project": "test",
            "convention": "docs/wiki-structure.yaml",
            "artifacts": [
                {
                    "name": "Guide",
                    "type": "prose_docs",
                    "model": "claude",
                },
            ],
        }
        write_plan_yaml(plan, plan_path)
        content = plan_path.read_text()
        assert "# Documentation plan" in content
        assert "prose_docs" in content

        # Verify it's valid YAML
        yaml = YAML()
        with open(plan_path) as f:
            loaded = yaml.load(f)
        assert loaded["project"] == "test"

    def test_creates_parent_dirs(self, tmp_path: Path) -> None:
        plan_path = tmp_path / "nested" / "plan.yaml"
        write_plan_yaml({"project": "test", "artifacts": []}, plan_path)
        assert plan_path.exists()

    def test_respects_developer_edits(self, tmp_path: Path) -> None:
        """AC: Developer edits to plan.yaml respected by downstream docs:auto."""
        plan_path = tmp_path / "plan.yaml"
        yaml = YAML()

        # Initial plan
        initial = {
            "project": "myproject",
            "convention": "docs/wiki-structure.yaml",
            "artifacts": [
                {"name": "Guide", "type": "prose_docs", "model": "claude"},
                {"name": "API", "type": "api_reference", "model": "gpt-4o"},
            ],
        }
        with open(plan_path, "w") as f:
            yaml.dump(initial, f)

        # Developer removes api_reference, changes prose model
        edited = {
            "project": "myproject",
            "convention": "docs/wiki-structure.yaml",
            "artifacts": [
                {"name": "Guide", "type": "prose_docs", "model": "gpt-4o"},
            ],
        }
        with open(plan_path, "w") as f:
            yaml.dump(edited, f)

        # Re-run generate_plan with both proposals
        proposals = [
            _make_proposal("prose_docs", "claude", 0.9),
            _make_proposal("api_reference", "gpt-4o", 0.8),
        ]
        plan = generate_plan("myproject", proposals, plan_path)

        # prose_docs: model override (gpt-4o) preserved from user edit
        prose = [a for a in plan["artifacts"] if a["type"] == "prose_docs"]
        assert prose[0]["model"] == "gpt-4o"

        # api_reference: re-added since it's a new proposal (user removed it,
        # but signal detection found it again — this is correct behavior;
        # the user can remove it again after review)
        api = [a for a in plan["artifacts"] if a["type"] == "api_reference"]
        assert len(api) == 1
