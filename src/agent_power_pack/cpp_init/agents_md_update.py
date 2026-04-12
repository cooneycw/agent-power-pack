"""AGENTS.md External Systems section writer (T088)."""

from __future__ import annotations

import re
from pathlib import Path

from agent_power_pack.logging import get_logger

log = get_logger("cpp_init.agents_md_update")

_SECTION_HEADER = "## External Systems"
_SECTION_PATTERN = re.compile(
    r"^## External Systems\s*\n(?:.*\n)*?(?=^## |\Z)",
    re.MULTILINE,
)


def _build_section(
    plane_url: str | None = None,
    plane_workspace: str | None = None,
    wikijs_url: str | None = None,
) -> str:
    """Build the External Systems markdown section."""
    lines = [f"{_SECTION_HEADER}\n"]

    if plane_url or wikijs_url:
        lines.append("Configured external integrations:\n")

        if plane_url:
            lines.append(f"- **Plane**: `{plane_url}`")
            if plane_workspace:
                lines.append(f"  - Workspace: `{plane_workspace}`")

        if wikijs_url:
            lines.append(f"- **Wiki.js**: `{wikijs_url}`")
    else:
        lines.append("No external systems configured yet.")
        lines.append("Run `agent-power-pack init --reconfigure plane` or")
        lines.append("`agent-power-pack init --reconfigure wikijs` to set up integrations.")

    lines.append("")
    return "\n".join(lines)


def update_agents_md_external_systems(
    agents_md_path: Path,
    plane_url: str | None = None,
    plane_workspace: str | None = None,
    wikijs_url: str | None = None,
) -> None:
    """Append or update the External Systems section in AGENTS.md.

    If the section already exists, replace it in place.
    If it doesn't exist, append it at the end of the file.
    """
    if not agents_md_path.exists():
        msg = f"AGENTS.md not found: {agents_md_path}"
        raise FileNotFoundError(msg)

    content = agents_md_path.read_text()
    new_section = _build_section(plane_url, plane_workspace, wikijs_url)

    if _SECTION_PATTERN.search(content):
        # Replace existing section
        updated = _SECTION_PATTERN.sub(new_section, content)
        log.info("replaced External Systems section", path=str(agents_md_path))
    else:
        # Append at end
        if not content.endswith("\n"):
            content += "\n"
        updated = content + "\n" + new_section
        log.info("appended External Systems section", path=str(agents_md_path))

    agents_md_path.write_text(updated)
