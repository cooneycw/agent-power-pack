"""E2E test: verify stdio/HTTP transport for all 6 MCP servers.

Uses testcontainers to spin up the MCP container and verify each server
responds on its stdio/HTTP port (8080-8085).
"""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.e2e]

HTTP_PORTS = [8080, 8081, 8082, 8083, 8084, 8085]
SERVER_NAMES = [
    "second-opinion",
    "plane",
    "wikijs",
    "nano-banana",
    "playwright-persistent",
    "woodpecker",
]


@pytest.fixture(scope="module")
def mcp_container():
    """Start the MCP container via testcontainers."""
    try:
        from testcontainers.core.container import DockerContainer
    except ImportError:
        pytest.skip("testcontainers not available")

    container = (
        DockerContainer("agent-power-pack-mcp:latest")
        .with_exposed_ports(*HTTP_PORTS)
        .with_env("OPENAI_API_KEY", "test")
        .with_env("ANTHROPIC_API_KEY", "test")
        .with_env("GEMINI_API_KEY", "test")
        .with_env("PLANE_BASE_URL", "http://localhost:8081")
        .with_env("PLANE_API_TOKEN", "test")
        .with_env("WIKIJS_BASE_URL", "http://localhost:8082")
        .with_env("WIKIJS_API_TOKEN", "test")
        .with_env("WOODPECKER_SERVER_URL", "http://localhost:8085")
        .with_env("WOODPECKER_API_TOKEN", "test")
    )

    try:
        container.start()
        yield container
    except Exception:
        pytest.skip("requires running MCP container / Docker")
    finally:
        try:
            container.stop()
        except Exception:
            pass


@pytest.mark.parametrize("port,name", zip(HTTP_PORTS, SERVER_NAMES))
def test_healthz_stdio_port(mcp_container, port: int, name: str) -> None:
    """Each server responds to /healthz on its stdio/HTTP port."""
    import httpx

    mapped_port = mcp_container.get_exposed_port(port)
    host = mcp_container.get_container_host_ip()
    resp = httpx.get(f"http://{host}:{mapped_port}/healthz", timeout=10)
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["name"] == name
    assert "version" in data
