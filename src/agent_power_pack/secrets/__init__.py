"""Tiered secrets layer (FR-016a).

Resolution order: AwsSidecarTier -> EnvFileTier -> DotenvTier.
First available tier on ``get()`` wins; ``set()`` writes to the dev
tier (DotenvTier) unless an explicit tier is passed.
"""

from __future__ import annotations

from agent_power_pack.secrets.aws_sidecar_tier import AwsSidecarTier
from agent_power_pack.secrets.dotenv_tier import DotenvTier
from agent_power_pack.secrets.env_file_tier import EnvFileTier
from agent_power_pack.secrets.protocol import HealthStatus, NotWritable, SecretTier

__all__ = [
    "AwsSidecarTier",
    "DotenvTier",
    "EnvFileTier",
    "HealthStatus",
    "NotWritable",
    "SecretTier",
    "get_secret",
    "resolve_tiers",
    "set_secret",
]

_DEFAULT_TIER_ORDER: list[type[AwsSidecarTier | EnvFileTier | DotenvTier]] = [
    AwsSidecarTier,
    EnvFileTier,
    DotenvTier,
]


def resolve_tiers() -> list[SecretTier]:
    """Instantiate all tiers in priority order, returning only those that are available."""
    return [tier() for tier in _DEFAULT_TIER_ORDER if tier().is_available()]  # type: ignore[misc]


def get_secret(key: str) -> str | None:
    """Read a secret by walking tiers in priority order.

    Returns the value from the first available tier that has the key,
    or ``None`` if no tier has it.
    """
    for tier_cls in _DEFAULT_TIER_ORDER:
        tier = tier_cls()
        if not tier.is_available():
            continue
        value = tier.get(key)
        if value is not None:
            return value
    return None


def set_secret(key: str, value: str, *, tier: SecretTier | None = None) -> None:
    """Write a secret. Defaults to DotenvTier unless an explicit tier is passed.

    Raises ``NotWritable`` if the chosen tier does not support writes.
    """
    target = tier or DotenvTier()
    target.set(key, value)
