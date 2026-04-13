"""Asyncio-based supervisor that starts all 6 MCP servers with dual transports.

Each server runs on two ports:
  - stdio/HTTP (non-streaming): 8080-8085 (for Claude Code)
  - Streamable HTTP (with SSE compatibility): 9100-9105 (for Codex CLI)
"""

from __future__ import annotations

import asyncio
import signal
import sys

from agent_power_pack.logging import configure_logging, get_logger

from mcp_container.transports.dual import DualTransportRunner

log = get_logger("supervisor")

SERVER_CONFIG = [
    {"name": "second-opinion", "module": "mcp_container.servers.second_opinion", "http_port": 8080, "sse_port": 9100},
    {"name": "plane", "module": "mcp_container.servers.plane", "http_port": 8081, "sse_port": 9101},
    {"name": "wikijs", "module": "mcp_container.servers.wikijs", "http_port": 8082, "sse_port": 9102},
    {"name": "nano-banana", "module": "mcp_container.servers.nano_banana", "http_port": 8083, "sse_port": 9103},
    {"name": "playwright-persistent", "module": "mcp_container.servers.playwright_persistent", "http_port": 8084, "sse_port": 9104},
    {"name": "woodpecker", "module": "mcp_container.servers.woodpecker", "http_port": 8085, "sse_port": 9105},
]


def _import_create_server(module_path: str):
    """Dynamically import and return the create_server function from a server module."""
    import importlib

    mod = importlib.import_module(module_path)
    return mod.create_server


async def _run_server(config: dict) -> None:
    """Start a single server with dual transports."""
    name = config["name"]
    try:
        factory = _import_create_server(config["module"])
        mcp_server = factory()
        runner = DualTransportRunner(
            mcp_server=mcp_server,
            server_name=name,
            http_port=config["http_port"],
            sse_port=config["sse_port"],
        )
        await runner.run()
    except Exception:
        log.exception("server_failed", server=name)
        raise


async def main() -> None:
    """Start all MCP servers concurrently."""
    configure_logging()
    log.info("supervisor_starting", server_count=len(SERVER_CONFIG))

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(_shutdown()))

    tasks = [asyncio.create_task(_run_server(cfg), name=cfg["name"]) for cfg in SERVER_CONFIG]

    log.info("all_servers_started")
    await asyncio.gather(*tasks)


async def _shutdown() -> None:
    """Graceful shutdown on SIGTERM/SIGINT."""
    log.info("shutdown_requested")
    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    asyncio.get_running_loop().stop()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("supervisor_stopped")
        sys.exit(0)
