"""Core pydantic models for the agent-power-pack skill manifest system.

Entities: Runtime, McpToolRef, Attribution, SkillManifest.
See specs/001-foundation/data-model.md for the canonical field definitions.
"""

from __future__ import annotations

import re
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class Runtime(str, Enum):
    """First-class runtimes supported by agent-power-pack (Constitution Principle I)."""

    CLAUDE_CODE = "claude-code"
    CODEX_CLI = "codex-cli"
    GEMINI_CLI = "gemini-cli"
    CURSOR = "cursor"


# The canonical set every manifest must declare.
CANONICAL_RUNTIMES: frozenset[Runtime] = frozenset(Runtime)

VALID_FAMILIES: frozenset[str] = frozenset(
    {
        "flow",
        "spec",
        "cicd",
        "docs",
        "security",
        "secrets",
        "qa",
        "agents-md",
        "second-opinion",
        "issue",
        "wiki",
        "project",
        "grill",
    }
)

VALID_MCP_SERVERS: frozenset[str] = frozenset(
    {
        "second-opinion",
        "plane",
        "wikijs",
        "nano-banana",
        "playwright",
        "woodpecker",
    }
)

_NAME_RE = re.compile(r"^[a-z][a-z0-9_-]*$")
_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


class McpToolRef(BaseModel):
    """A typed pointer from a skill manifest to an MCP tool."""

    server: str
    tool: str

    @field_validator("server")
    @classmethod
    def _server_must_be_known(cls, v: str) -> str:
        if v not in VALID_MCP_SERVERS:
            msg = f"Unknown MCP server '{v}'; must be one of {sorted(VALID_MCP_SERVERS)}"
            raise ValueError(msg)
        return v


class Attribution(BaseModel):
    """Required metadata for vendored skills (under vendor/skills/)."""

    source: str
    commit_sha: str
    license: str
    author: Optional[str] = None

    @field_validator("commit_sha")
    @classmethod
    def _sha_format(cls, v: str) -> str:
        if not _SHA_RE.match(v):
            msg = f"commit_sha must be a 40-character hex string, got '{v}'"
            raise ValueError(msg)
        return v


class SkillManifest(BaseModel):
    """Source of truth for every skill in the catalog.

    Location on disk: manifests/<family>/<name>.yaml
    """

    name: str
    family: str
    description: str
    triggers: list[str] = Field(min_length=1)
    runtimes: list[Runtime]
    prompt: str
    mcp_tools: list[McpToolRef] = Field(default_factory=list)
    attribution: Optional[Attribution] = None
    order: int = 100

    @field_validator("name")
    @classmethod
    def _name_format(cls, v: str) -> str:
        if not _NAME_RE.match(v):
            msg = f"name must match ^[a-z][a-z0-9_-]*$, got '{v}'"
            raise ValueError(msg)
        return v

    @field_validator("family")
    @classmethod
    def _family_must_be_valid(cls, v: str) -> str:
        if v not in VALID_FAMILIES:
            msg = f"Unknown family '{v}'; must be one of {sorted(VALID_FAMILIES)}"
            raise ValueError(msg)
        return v
