"""Generator for runtime-specific instruction files from AGENTS.md (T039)."""

from __future__ import annotations

from pathlib import Path

from agent_power_pack.linter.document import load_agents_md
from agent_power_pack.linter.generated_check import GENERATED_HEADER, HASH_PREFIX

# Runtime → filename mapping
RUNTIME_FILE_MAP: dict[str, str] = {
    "claude-code": "CLAUDE.md",
    "gemini-cli": "GEMINI.md",
    "cursor": ".cursorrules",
}


def generate_instruction_files(repo_root: Path) -> list[Path]:
    """Generate instruction files from AGENTS.md. Returns list of written paths."""
    agents_md = repo_root / "AGENTS.md"
    if not agents_md.exists():
        return []

    doc = load_agents_md(agents_md)
    content = agents_md.read_text()

    written: list[Path] = []
    for _runtime, filename in RUNTIME_FILE_MAP.items():
        out_path = repo_root / filename
        out_path.write_text(
            f"{GENERATED_HEADER}\n"
            f"{HASH_PREFIX}{doc.content_hash} -->\n"
            f"{content}"
        )
        written.append(out_path)

    return written
