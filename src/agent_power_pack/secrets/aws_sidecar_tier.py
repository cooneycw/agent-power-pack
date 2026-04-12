"""AwsSidecarTier — production secrets tier via aws-secretsmanager-agent sidecar (data-model.md §10)."""

from __future__ import annotations

from typing import Literal

import httpx

from agent_power_pack.secrets.protocol import HealthStatus, NotWritable

_DEFAULT_BASE_URL = "http://127.0.0.1:2773"
_TIMEOUT = 5.0


class AwsSidecarTier:
    """Reads secrets through the local ``aws-secretsmanager-agent`` HTTP endpoint.

    The sidecar is the official Rust-based
    `aws-secretsmanager-agent <https://github.com/awslabs/aws-secretsmanager-agent>`_,
    started alongside the MCP container via ``compose.yaml``.

    This tier is **read-only** — writes raise ``NotWritable``.
    Every production read MUST traverse the sidecar (spec FR-016a).
    """

    name: Literal["aws-sidecar"] = "aws-sidecar"

    def __init__(self, base_url: str = _DEFAULT_BASE_URL) -> None:
        self._base_url = base_url.rstrip("/")

    def is_available(self) -> bool:
        return self.health() == HealthStatus.HEALTHY

    def get(self, key: str) -> str | None:
        try:
            resp = httpx.get(
                f"{self._base_url}/secretsmanager/get",
                params={"secretId": key},
                timeout=_TIMEOUT,
            )
        except httpx.ConnectError:
            return None
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.text

    def set(self, key: str, value: str) -> None:
        msg = (
            "AwsSidecarTier is read-only. "
            "Use DotenvTier for writes or pass --tier dotenv."
        )
        raise NotWritable(msg)

    def health(self) -> HealthStatus:
        try:
            resp = httpx.get(f"{self._base_url}/healthz", timeout=_TIMEOUT)
            if resp.status_code == 200:
                return HealthStatus.HEALTHY
            return HealthStatus.UNHEALTHY
        except httpx.ConnectError:
            return HealthStatus.UNCONFIGURED
