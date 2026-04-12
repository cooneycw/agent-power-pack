"""Cursor adapter stub — raises AdapterNotImplemented at v0.1.0.

Per spec FR-002, the Cursor adapter ships before v1.0.0. Manifests already
declare cursor in their runtimes list (Principle I) so coverage is validated
at manifest time.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from agent_power_pack.manifest.schema import SkillManifest
from adapters import AdapterNotImplemented
from adapters.report import InstallReport


class CursorStub:
    """Stub adapter that raises on install — Cursor support lands before v1.0.0."""

    runtime_id: Literal["cursor"] = "cursor"
    display_name: str = "Cursor"

    def install(
        self,
        manifests: list[SkillManifest],
        target_dir: Path,
        *,
        mode: Literal["project", "user"] = "project",
    ) -> InstallReport:
        raise AdapterNotImplemented("cursor adapter lands before v1.0.0")
