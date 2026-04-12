"""Wiki.js MCP server — page CRUD and search via GraphQL v2 API."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP

from agent_power_pack.logging import get_logger

log = get_logger("servers.wikijs")

_OPS_DIR = Path(__file__).parent / "operations"


def _get_config() -> tuple[str, str]:
    base_url = os.environ.get("WIKIJS_BASE_URL", "").rstrip("/")
    token = os.environ.get("WIKIJS_API_TOKEN", "")
    if not base_url or not token:
        raise ValueError("WIKIJS_BASE_URL and WIKIJS_API_TOKEN must be set")
    return base_url, token


def _load_op(name: str) -> str:
    return (_OPS_DIR / f"{name}.graphql").read_text()


async def _gql_request(query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
    base_url, token = _get_config()
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{base_url}/graphql",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json={"query": query, "variables": variables or {}},
        )
        resp.raise_for_status()
        data = resp.json()
        if "errors" in data and data["errors"]:
            raise RuntimeError(f"GraphQL errors: {data['errors']}")
        return data.get("data", {})


def create_server() -> FastMCP:
    mcp = FastMCP("wikijs")

    @mcp.tool()
    async def list_pages(
        space: str | None = None,
        tag: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """List Wiki.js pages, optionally filtered by space or tag."""
        query = _load_op("list_pages")
        variables: dict[str, Any] = {"limit": limit}
        if space:
            variables["path"] = space
        if tag:
            variables["tags"] = [tag]
        data = await _gql_request(query, variables)
        return data.get("pages", {}).get("list", [])

    @mcp.tool()
    async def create_page(
        path: str,
        title: str,
        content: str,
        description: str = "",
        tags: list[str] | None = None,
        is_published: bool = True,
    ) -> dict[str, Any]:
        """Create a new Wiki.js page."""
        query = _load_op("create_page")
        variables = {
            "path": path,
            "title": title,
            "content": content,
            "description": description,
            "tags": tags or [],
            "isPublished": is_published,
            "editor": "markdown",
            "locale": "en",
        }
        data = await _gql_request(query, variables)
        return data.get("pages", {}).get("create", {})

    @mcp.tool()
    async def update_page(
        page_id: int,
        content: str,
        title: str | None = None,
        description: str | None = None,
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        """Update an existing Wiki.js page."""
        query = _load_op("update_page")
        variables: dict[str, Any] = {"id": page_id, "content": content}
        if title is not None:
            variables["title"] = title
        if description is not None:
            variables["description"] = description
        if tags is not None:
            variables["tags"] = tags
        data = await _gql_request(query, variables)
        return data.get("pages", {}).get("update", {})

    @mcp.tool()
    async def delete_page(page_id: int) -> dict[str, Any]:
        """Delete a Wiki.js page by ID."""
        query = _load_op("delete_page")
        data = await _gql_request(query, {"id": page_id})
        return data.get("pages", {}).get("delete", {})

    @mcp.tool()
    async def search(query_text: str, limit: int = 20) -> list[dict[str, Any]]:
        """Full-text search across Wiki.js pages."""
        query = _load_op("search")
        data = await _gql_request(query, {"query": query_text, "limit": limit})
        return data.get("pages", {}).get("search", {}).get("results", [])

    @mcp.tool()
    async def publish_c4(
        path: str,
        title: str,
        diagrams: str,
    ) -> dict[str, Any]:
        """Publish C4 architecture diagrams as a Wiki.js page."""
        content = f"# {title}\n\n{diagrams}"
        return await create_page(path=path, title=title, content=content, tags=["c4", "architecture"])

    return mcp
