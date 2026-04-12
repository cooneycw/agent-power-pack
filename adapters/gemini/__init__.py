"""Gemini CLI adapter stub — raises AdapterNotImplemented at v0.1.0.

Per spec FR-002, the Gemini adapter ships before v1.0.0. Manifests already
declare gemini-cli in their runtimes list (Principle I) so coverage is
validated at manifest time.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from agent_power_pack.manifest.schema import SkillManifest
from adapters import AdapterNotImplemented
from adapters.report import InstallReport


class GeminiStub:
    """Stub adapter that raises on install — Gemini CLI support lands before v1.0.0."""

    runtime_id: Literal["gemini-cli"] = "gemini-cli"
    display_name: str = "Gemini CLI"

    def install(
        self,
        manifests: list[SkillManifest],
        target_dir: Path,
        *,
        mode: Literal["project", "user"] = "project",
    ) -> InstallReport:
        raise AdapterNotImplemented("gemini-cli adapter lands before v1.0.0")
