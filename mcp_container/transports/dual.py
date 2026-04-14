"""Dual-transport runner for MCP servers.

Provides both stdio/HTTP (non-streaming) and streamable HTTP transports
for each MCP server instance.  The streamable-HTTP listener also serves
SSE for backward compatibility.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route
from uvicorn import Config, Server

from agent_power_pack.logging import get_logger

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

log = get_logger("transports.dual")


def _build_health_app(server_name: str, version: str = "0.1.0") -> Starlette:
    """Build a minimal Starlette app with a /healthz endpoint."""

    async def healthz(_request: Request) -> JSONResponse:
        return JSONResponse({"ok": True, "name": server_name, "version": version})

    return Starlette(routes=[Route("/healthz", healthz)])


class DualTransportRunner:
    """Runs a single FastMCP server on two ports: HTTP and Streamable HTTP."""

    def __init__(
        self,
        mcp_server: FastMCP,
        server_name: str,
        http_port: int,
        sse_port: int,
    ) -> None:
        self.mcp_server = mcp_server
        self.server_name = server_name
        self.http_port = http_port
        self.sse_port = sse_port

    async def run(self) -> None:
        """Start both transports concurrently."""
        log.info(
            "starting_dual_transport",
            server=self.server_name,
            http_port=self.http_port,
            sse_port=self.sse_port,
        )
        await asyncio.gather(
            self._run_http(),
            self._run_sse(),
        )

    async def _run_http(self) -> None:
        """Run stdio/HTTP non-streaming transport with /healthz."""
        health_app = _build_health_app(self.server_name)

        # Mount the MCP streamable-http endpoint alongside health
        try:
            # FastMCP has .sse_app() or similar — we use streamable HTTP
            mcp_app = self.mcp_server.streamable_http_app()
        except (AttributeError, TypeError):
            # Fallback: use SSE app for the HTTP port too
            try:
                mcp_app = self.mcp_server.sse_app()
            except (AttributeError, TypeError):
                mcp_app = None

        if mcp_app is not None:
            # Merge health route into the MCP app
            from starlette.routing import Mount, Route as SRoute

            health_route = SRoute("/healthz", _build_health_app(self.server_name).routes[0].endpoint)
            if hasattr(mcp_app, "routes"):
                mcp_app.routes.insert(0, health_route)
                app = mcp_app
            else:
                app = Starlette(
                    routes=[
                        health_route,
                        Mount("/", app=mcp_app),
                    ]
                )
        else:
            app = health_app

        config = Config(app=app, host="0.0.0.0", port=self.http_port, log_level="warning")
        server = Server(config)
        await server.serve()

    async def _run_sse(self) -> None:
        """Run streamable HTTP transport (with SSE compatibility) and /healthz."""
        health_app = _build_health_app(self.server_name)

        try:
            mcp_app = self.mcp_server.sse_app()
        except (AttributeError, TypeError):
            mcp_app = None

        if mcp_app is not None:
            from starlette.routing import Mount, Route as SRoute

            health_route = SRoute("/healthz", _build_health_app(self.server_name).routes[0].endpoint)
            if hasattr(mcp_app, "routes"):
                mcp_app.routes.insert(0, health_route)
                app = mcp_app
            else:
                app = Starlette(
                    routes=[
                        health_route,
                        Mount("/", app=mcp_app),
                    ]
                )
        else:
            app = health_app

        config = Config(app=app, host="0.0.0.0", port=self.sse_port, log_level="warning")
        server = Server(config)
        await server.serve()
