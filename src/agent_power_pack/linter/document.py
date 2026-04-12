"""AgentsMdDocument loader (T033).

Parses AGENTS.md into a structured dataclass for downstream lint checks.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class AgentsMdDocument:
    """Parsed representation of an AGENTS.md file."""

    sections: dict[str, str] = field(default_factory=dict)
    referenced_make_targets: set[str] = field(default_factory=set)
    referenced_commands: set[str] = field(default_factory=set)
    referenced_docker_services: set[str] = field(default_factory=set)
    referenced_ci_files: set[str] = field(default_factory=set)
    content_hash: str = ""


# Regex patterns
_H2_RE = re.compile(r"^##\s+(.+)$", re.MULTILINE)
_MAKE_TARGET_RE = re.compile(r"`make\s+([\w-]+)`")
_SLASH_CMD_RE = re.compile(r"`/([\w-]+)`")
_DOCKER_SERVICE_RE = re.compile(r"`docker\s+compose\s+[^`]*\s+([\w-]+)`")
_CI_FILE_RE = re.compile(r"`(\.[\w./-]+\.ya?ml)`")


def load_agents_md(path: Path) -> AgentsMdDocument:
    """Load and parse an AGENTS.md file into an AgentsMdDocument."""
    raw = path.read_bytes()
    text = raw.decode("utf-8")
    content_hash = hashlib.sha256(raw).hexdigest()

    # Split into H2 sections
    sections: dict[str, str] = {}
    matches = list(_H2_RE.finditer(text))
    for i, m in enumerate(matches):
        title = m.group(1).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        sections[title] = text[start:end].strip()

    # Extract references from the full text
    make_targets = set(_MAKE_TARGET_RE.findall(text))
    commands = set(_SLASH_CMD_RE.findall(text))
    docker_services = set(_DOCKER_SERVICE_RE.findall(text))
    ci_files = set(_CI_FILE_RE.findall(text))

    return AgentsMdDocument(
        sections=sections,
        referenced_make_targets=make_targets,
        referenced_commands=commands,
        referenced_docker_services=docker_services,
        referenced_ci_files=ci_files,
        content_hash=content_hash,
    )
