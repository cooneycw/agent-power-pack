"""EnvFileTier — secrets tier backed by a Docker/systemd-style env file (data-model.md §10)."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from agent_power_pack.secrets.protocol import HealthStatus, NotWritable


class EnvFileTier:
    """Reads secrets from a plain ``KEY=VALUE`` env file.

    This is the middle tier in the resolution order
    (aws-sidecar -> env-file -> dotenv). Env files are typically
    mounted into containers via ``docker run --env-file`` or
    systemd ``EnvironmentFile=``. They use no shell interpolation
    — values are taken literally.

    This tier is **read-only** by default: container-mounted env files
    should not be mutated at runtime. Writes raise ``NotWritable``.
    """

    name: Literal["env-file"] = "env-file"

    def __init__(self, env_file_path: Path | None = None) -> None:
        self._path = env_file_path or Path("/run/secrets/env")

    def is_available(self) -> bool:
        return self._path.is_file()

    def get(self, key: str) -> str | None:
        if not self._path.is_file():
            return None
        for line in self._path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            k, _, v = line.partition("=")
            if k.strip() == key:
                return v.strip()
        return None

    def set(self, key: str, value: str) -> None:
        msg = (
            f"EnvFileTier is read-only (file: {self._path}). "
            "Use DotenvTier for writes or pass --tier dotenv."
        )
        raise NotWritable(msg)

    def health(self) -> HealthStatus:
        if not self._path.is_file():
            return HealthStatus.UNCONFIGURED
        return HealthStatus.HEALTHY
