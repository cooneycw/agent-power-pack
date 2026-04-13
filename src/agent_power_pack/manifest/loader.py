"""YAML loader for skill manifests using ruamel.yaml round-trip mode.

Preserves comments, field ordering, and whitespace for lossless round-trips.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Union

from ruamel.yaml import YAML

from agent_power_pack.manifest.schema import SkillManifest


def _make_yaml() -> YAML:
    """Create a ruamel.yaml instance configured for round-trip fidelity."""
    yaml = YAML(typ="rt")
    yaml.preserve_quotes = True
    yaml.default_flow_style = False
    yaml.width = 120
    return yaml


def load_manifest(source: Union[str, Path]) -> SkillManifest:
    """Load and validate a single skill manifest from a YAML file.

    Args:
        source: Path to a .yaml manifest file.

    Returns:
        A validated SkillManifest instance.

    Raises:
        FileNotFoundError: If the source path does not exist.
        pydantic.ValidationError: If the YAML content fails schema validation.
    """
    path = Path(source)
    yaml = _make_yaml()
    data = yaml.load(path)
    return SkillManifest.model_validate(dict(data))


def load_manifest_from_string(text: str) -> SkillManifest:
    """Load and validate a skill manifest from a YAML string.

    Args:
        text: YAML content as a string.

    Returns:
        A validated SkillManifest instance.
    """
    yaml = _make_yaml()
    data = yaml.load(text)
    return SkillManifest.model_validate(dict(data))


def load_all_manifests(manifests_dir: Union[str, Path]) -> list[SkillManifest]:
    """Load all .yaml manifests under a directory tree.

    Args:
        manifests_dir: Root directory to scan (typically ``manifests/``).

    Returns:
        A list of validated SkillManifest instances, sorted by (family, order, name).
    """
    root = Path(manifests_dir)
    manifests: list[SkillManifest] = []
    for yaml_path in sorted(root.rglob("*.yaml")):
        manifests.append(load_manifest(yaml_path))
    return sorted(manifests, key=lambda m: (m.family, m.order, m.name))


def dump_manifest(manifest: SkillManifest, dest: Union[str, Path]) -> None:
    """Serialize a SkillManifest back to YAML, preserving round-trip style.

    Args:
        manifest: The manifest to write.
        dest: Output file path.
    """
    path = Path(dest)
    path.parent.mkdir(parents=True, exist_ok=True)
    yaml = _make_yaml()
    yaml.dump(manifest.model_dump(mode="json"), path)


def load_raw_yaml(source: Union[str, Path]) -> dict[str, Any]:
    """Load raw YAML data preserving comments and ordering (for round-trip tests).

    Args:
        source: Path to a .yaml file.

    Returns:
        A ruamel.yaml CommentedMap (dict-like) with comments preserved.
    """
    yaml = _make_yaml()
    return yaml.load(Path(source))  # type: ignore[no-any-return]


def dump_raw_yaml(data: dict[str, Any], dest: Union[str, Path]) -> None:
    """Dump raw YAML data preserving comments and ordering.

    Args:
        data: A ruamel.yaml CommentedMap or dict.
        dest: Output file path.
    """
    path = Path(dest)
    path.parent.mkdir(parents=True, exist_ok=True)
    yaml = _make_yaml()
    yaml.dump(data, path)
