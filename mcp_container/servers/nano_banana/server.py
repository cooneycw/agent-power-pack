"""Nano-banana MCP server — diagram rendering for PlantUML and Mermaid."""

from __future__ import annotations

import base64
import zlib

import httpx
from mcp.server.fastmcp import FastMCP

from agent_power_pack.logging import get_logger

log = get_logger("servers.nano_banana")

_PLANTUML_SERVER = "https://www.plantuml.com/plantuml"
_KROKI_SERVER = "https://kroki.io"


def _plantuml_encode(source: str) -> str:
    """Encode PlantUML source for the PlantUML web service URL."""
    compressed = zlib.compress(source.encode("utf-8"))[2:-4]
    return base64.urlsafe_b64encode(compressed).decode("ascii")


async def _render_plantuml(source: str, fmt: str = "svg") -> str:
    """Render PlantUML diagram via the public PlantUML server."""
    encoded = _plantuml_encode(source)
    url = f"{_PLANTUML_SERVER}/{fmt}/{encoded}"
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        if fmt == "svg":
            return resp.text
        return base64.b64encode(resp.content).decode("ascii")


async def _render_mermaid(source: str, fmt: str = "svg") -> str:
    """Render Mermaid diagram via the Kroki service."""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{_KROKI_SERVER}/mermaid/{fmt}",
            headers={"Content-Type": "text/plain"},
            content=source,
        )
        resp.raise_for_status()
        if fmt == "svg":
            return resp.text
        return base64.b64encode(resp.content).decode("ascii")


def create_server() -> FastMCP:
    mcp = FastMCP("nano-banana")

    @mcp.tool()
    async def diagram_c4(source: str, format: str = "svg") -> str:
        """Render a C4 diagram from PlantUML source.

        Args:
            source: PlantUML C4 diagram source code.
            format: Output format — 'svg' or 'png'.
        """
        if not source.strip().startswith("@start"):
            source = f"@startuml\n{source}\n@enduml"
        return await _render_plantuml(source, format)

    @mcp.tool()
    async def diagram_sequence(source: str, format: str = "svg") -> str:
        """Render a sequence diagram.

        Supports both PlantUML (@startuml) and Mermaid (sequenceDiagram) syntax.
        """
        if source.strip().startswith("sequenceDiagram"):
            return await _render_mermaid(source, format)
        if not source.strip().startswith("@start"):
            source = f"@startuml\n{source}\n@enduml"
        return await _render_plantuml(source, format)

    @mcp.tool()
    async def diagram_flowchart(source: str, format: str = "svg") -> str:
        """Render a flowchart diagram.

        Supports both PlantUML and Mermaid (graph/flowchart) syntax.
        """
        trimmed = source.strip()
        if trimmed.startswith(("graph ", "flowchart ")):
            return await _render_mermaid(source, format)
        if not trimmed.startswith("@start"):
            source = f"@startuml\n{source}\n@enduml"
        return await _render_plantuml(source, format)

    @mcp.tool()
    async def diagram_er(source: str, format: str = "svg") -> str:
        """Render an entity-relationship diagram.

        Supports both PlantUML and Mermaid (erDiagram) syntax.
        """
        if source.strip().startswith("erDiagram"):
            return await _render_mermaid(source, format)
        if not source.strip().startswith("@start"):
            source = f"@startuml\n{source}\n@enduml"
        return await _render_plantuml(source, format)

    return mcp
