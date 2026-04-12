"""GrillTriggerConfig pydantic model + YAML loader (T063).

Loads grill-yourself trigger thresholds from .specify/grill-triggers.yaml,
falling back to sensible defaults when no config file is present.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field
from ruamel.yaml import YAML

from agent_power_pack.logging import get_logger

log = get_logger("grill.config")


class GrillTriggerConfig(BaseModel):
    """Thresholds that decide whether grill-yourself should fire."""

    max_lines: int = 200
    max_files: int = 5
    exclude_globs: list[str] = Field(default_factory=list)


def load_grill_config(config_path: Path | None = None) -> GrillTriggerConfig:
    """Load from .specify/grill-triggers.yaml, falling back to defaults."""
    if config_path is None:
        config_path = Path(".specify/grill-triggers.yaml")
    if not config_path.exists():
        log.debug("grill config not found, using defaults", path=str(config_path))
        return GrillTriggerConfig()
    yaml = YAML()
    data = yaml.load(config_path)
    if data is None:
        return GrillTriggerConfig()
    return GrillTriggerConfig(**data)
