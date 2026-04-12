"""Woodpecker CI MCP server — pipeline management via REST API."""

from __future__ import annotations

import os
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP

from agent_power_pack.logging import get_logger

log = get_logger("servers.woodpecker")


def _get_config() -> tuple[str, str]:
    server_url = os.environ.get("WOODPECKER_SERVER_URL", "").rstrip("/")
    token = os.environ.get("WOODPECKER_API_TOKEN", "")
    if not server_url or not token:
        raise ValueError("WOODPECKER_SERVER_URL and WOODPECKER_API_TOKEN must be set")
    return server_url, token


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def create_server() -> FastMCP:
    mcp = FastMCP("woodpecker")

    @mcp.tool()
    async def health_check() -> dict[str, Any]:
        """Check Woodpecker server health."""
        server_url, token = _get_config()
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{server_url}/api/user", headers=_headers(token))
            resp.raise_for_status()
            return {"healthy": True, "user": resp.json().get("login", "unknown")}

    @mcp.tool()
    async def list_repos() -> list[dict[str, Any]]:
        """List all repositories configured in Woodpecker."""
        server_url, token = _get_config()
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(f"{server_url}/api/user/repos", headers=_headers(token))
            resp.raise_for_status()
            return resp.json()

    @mcp.tool()
    async def list_pipelines(repo_id: int, page: int = 1) -> list[dict[str, Any]]:
        """List pipelines for a repository."""
        server_url, token = _get_config()
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{server_url}/api/repos/{repo_id}/pipelines",
                headers=_headers(token),
                params={"page": page},
            )
            resp.raise_for_status()
            return resp.json()

    @mcp.tool()
    async def get_pipeline(repo_id: int, number: int) -> dict[str, Any]:
        """Get details of a specific pipeline."""
        server_url, token = _get_config()
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{server_url}/api/repos/{repo_id}/pipelines/{number}",
                headers=_headers(token),
            )
            resp.raise_for_status()
            return resp.json()

    @mcp.tool()
    async def create_pipeline(
        repo_id: int,
        branch: str | None = None,
        variables: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Trigger a new pipeline run for a repository."""
        server_url, token = _get_config()
        body: dict[str, Any] = {}
        if branch:
            body["branch"] = branch
        if variables:
            body["variables"] = variables

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{server_url}/api/repos/{repo_id}/pipelines",
                headers=_headers(token),
                json=body,
            )
            resp.raise_for_status()
            return resp.json()

    @mcp.tool()
    async def cancel_pipeline(repo_id: int, number: int) -> dict[str, Any]:
        """Cancel a running pipeline."""
        server_url, token = _get_config()
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{server_url}/api/repos/{repo_id}/pipelines/{number}/cancel",
                headers=_headers(token),
            )
            resp.raise_for_status()
            return resp.json()

    @mcp.tool()
    async def approve_pipeline(repo_id: int, number: int) -> dict[str, Any]:
        """Approve a blocked pipeline."""
        server_url, token = _get_config()
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{server_url}/api/repos/{repo_id}/pipelines/{number}/approve",
                headers=_headers(token),
            )
            resp.raise_for_status()
            return resp.json()

    @mcp.tool()
    async def get_pipeline_logs(
        repo_id: int,
        number: int,
        step: int | None = None,
    ) -> list[dict[str, Any]] | str:
        """Get logs for a pipeline, optionally for a specific step."""
        server_url, token = _get_config()
        async with httpx.AsyncClient(timeout=30) as client:
            if step is not None:
                resp = await client.get(
                    f"{server_url}/api/repos/{repo_id}/pipelines/{number}/logs/{step}",
                    headers=_headers(token),
                )
            else:
                # Get all steps first, then fetch logs for each
                pipeline = await get_pipeline(repo_id, number)
                all_logs: list[dict[str, Any]] = []
                for workflow in pipeline.get("workflows", []):
                    for child in workflow.get("children", []):
                        step_id = child.get("id") or child.get("pid")
                        if step_id is None:
                            continue
                        resp = await client.get(
                            f"{server_url}/api/repos/{repo_id}/pipelines/{number}/logs/{step_id}",
                            headers=_headers(token),
                        )
                        if resp.status_code == 200:
                            all_logs.append({"step": step_id, "logs": resp.json()})
                return all_logs

            resp.raise_for_status()
            return resp.json()

    return mcp
