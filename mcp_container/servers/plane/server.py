"""Plane MCP server — issue tracking via Plane REST API v1."""

from __future__ import annotations

import os
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP

from agent_power_pack.logging import get_logger

log = get_logger("servers.plane")


def _get_config() -> tuple[str, str]:
    base_url = os.environ.get("PLANE_BASE_URL", "").rstrip("/")
    token = os.environ.get("PLANE_API_TOKEN", "")
    if not base_url or not token:
        raise ValueError("PLANE_BASE_URL and PLANE_API_TOKEN must be set")
    return base_url, token


def _headers(token: str) -> dict[str, str]:
    return {"X-API-Key": token, "Content-Type": "application/json"}


def create_server() -> FastMCP:
    mcp = FastMCP("plane")

    @mcp.tool()
    async def list_workspaces() -> list[dict[str, Any]]:
        """List all Plane workspaces accessible to the configured API token."""
        base_url, token = _get_config()
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(f"{base_url}/api/v1/workspaces/", headers=_headers(token))
            resp.raise_for_status()
            return resp.json().get("results", resp.json())

    @mcp.tool()
    async def create_issue(
        workspace: str,
        project: str,
        title: str,
        description: str = "",
        priority: str | None = None,
        assignees: list[str] | None = None,
        labels: list[str] | None = None,
    ) -> dict[str, Any]:
        """Create an issue in a Plane project."""
        base_url, token = _get_config()
        body: dict[str, Any] = {"name": title}
        if description:
            body["description_html"] = f"<p>{description}</p>"
        if priority:
            body["priority"] = priority
        if assignees:
            body["assignees"] = assignees
        if labels:
            body["labels"] = labels

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{base_url}/api/v1/workspaces/{workspace}/projects/{project}/issues/",
                headers=_headers(token),
                json=body,
            )
            resp.raise_for_status()
            return resp.json()

    @mcp.tool()
    async def update_issue(
        workspace: str,
        project: str,
        issue_id: str,
        title: str | None = None,
        description: str | None = None,
        priority: str | None = None,
        state: str | None = None,
    ) -> dict[str, Any]:
        """Update an existing Plane issue."""
        base_url, token = _get_config()
        body: dict[str, Any] = {}
        if title is not None:
            body["name"] = title
        if description is not None:
            body["description_html"] = f"<p>{description}</p>"
        if priority is not None:
            body["priority"] = priority
        if state is not None:
            body["state"] = state

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.patch(
                f"{base_url}/api/v1/workspaces/{workspace}/projects/{project}/issues/{issue_id}/",
                headers=_headers(token),
                json=body,
            )
            resp.raise_for_status()
            return resp.json()

    @mcp.tool()
    async def list_issues(
        workspace: str,
        project: str,
        state: str | None = None,
        priority: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """List issues in a Plane project, optionally filtered."""
        base_url, token = _get_config()
        params: dict[str, Any] = {"per_page": limit}
        if state:
            params["state__name"] = state
        if priority:
            params["priority"] = priority

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{base_url}/api/v1/workspaces/{workspace}/projects/{project}/issues/",
                headers=_headers(token),
                params=params,
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("results", data)

    @mcp.tool()
    async def close_issue(
        workspace: str,
        project: str,
        issue_id: str,
    ) -> dict[str, Any]:
        """Close a Plane issue by setting its state group to 'completed'."""
        return await update_issue(workspace, project, issue_id, state="done")

    @mcp.tool()
    async def list_cycles(
        workspace: str,
        project: str,
    ) -> list[dict[str, Any]]:
        """List cycles (sprints) in a Plane project."""
        base_url, token = _get_config()
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{base_url}/api/v1/workspaces/{workspace}/projects/{project}/cycles/",
                headers=_headers(token),
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("results", data)

    return mcp
