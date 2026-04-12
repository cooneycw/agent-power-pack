"""SecretTier Protocol and shared types (data-model.md §10)."""

from __future__ import annotations

from enum import Enum
from typing import Literal, Protocol, runtime_checkable


class HealthStatus(str, Enum):
    """Health probe result for a secrets tier."""

    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    UNCONFIGURED = "unconfigured"


class NotWritable(Exception):
    """Raised when a tier does not support writes (e.g. AWS sidecar in read-only mode)."""


@runtime_checkable
class SecretTier(Protocol):
    """Abstract interface for the tiered secrets layer.

    Tier selection order: AwsSidecarTier → EnvFileTier → DotenvTier.
    First available tier on ``get()`` wins; ``set()`` writes to the dev
    tier (DotenvTier) unless ``--tier`` is passed explicitly.
    """

    name: Literal["dotenv", "env-file", "aws-sidecar"]

    def is_available(self) -> bool: ...

    def get(self, key: str) -> str | None: ...

    def set(self, key: str, value: str) -> None: ...

    def health(self) -> HealthStatus: ...
