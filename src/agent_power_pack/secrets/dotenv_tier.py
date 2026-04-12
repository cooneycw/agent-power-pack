"""DotenvTier — dev-default secrets tier backed by a .env file (data-model.md §10)."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from dotenv import dotenv_values, set_key

from agent_power_pack.secrets.protocol import HealthStatus


class DotenvTier:
    """Reads and writes secrets via a ``.env`` file.

    This is the default dev tier. Writes always go here unless
    ``--tier`` overrides to another tier.
    """

    name: Literal["dotenv"] = "dotenv"

    def __init__(self, dotenv_path: Path | None = None) -> None:
        self._path = dotenv_path or self._find_dotenv()

    def is_available(self) -> bool:
        return self._path.exists()

    def get(self, key: str) -> str | None:
        if not self._path.exists():
            return None
        values = dotenv_values(self._path)
        return values.get(key)

    def set(self, key: str, value: str) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        if not self._path.exists():
            self._path.touch()
        success, _key, _value = set_key(str(self._path), key, value)
        if not success:
            msg = f"Failed to write {key} to {self._path}"
            raise OSError(msg)

    def health(self) -> HealthStatus:
        if not self._path.exists():
            return HealthStatus.UNCONFIGURED
        return HealthStatus.HEALTHY

    @staticmethod
    def _find_dotenv() -> Path:
        """Walk up from cwd to find a .env file, defaulting to cwd/.env."""
        current = Path.cwd()
        for parent in [current, *current.parents]:
            candidate = parent / ".env"
            if candidate.exists():
                return candidate
        return current / ".env"
