"""E2E test: verify both transports return identical results concurrently.

Connects to a single MCP server via both its HTTP and SSE ports
simultaneously and verifies they return consistent results.
"""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.e2e]


@pytest.fixture(scope="module")
def mcp_container():
    """Start the MCP container via testcontainers."""
    try:
        from testcontainers.core.container import DockerContainer
    except ImportError:
        pytest.skip("testcontainers not available")

    all_ports = [8080, 8081, 8082, 8083, 8084, 8085, 9100, 9101, 9102, 9103, 9104, 9105]
    container = (
        DockerContainer("agent-power-pack-mcp:latest")
        .with_exposed_ports(*all_ports)
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


_PAIRS = [
    ("second-opinion", 8080, 9100),
    ("plane", 8081, 9101),
    ("wikijs", 8082, 9102),
    ("nano-banana", 8083, 9103),
    ("playwright-persistent", 8084, 9104),
    ("woodpecker", 8085, 9105),
]


@pytest.mark.parametrize("name,http_port,sse_port", _PAIRS)
def test_dual_healthz_consistent(mcp_container, name: str, http_port: int, sse_port: int) -> None:
    """Both transports return identical /healthz responses for the same server."""
    import httpx

    host = mcp_container.get_container_host_ip()

    http_mapped = mcp_container.get_exposed_port(http_port)
    sse_mapped = mcp_container.get_exposed_port(sse_port)

    http_resp = httpx.get(f"http://{host}:{http_mapped}/healthz", timeout=10)
    sse_resp = httpx.get(f"http://{host}:{sse_mapped}/healthz", timeout=10)

    assert http_resp.status_code == 200
    assert sse_resp.status_code == 200

    http_data = http_resp.json()
    sse_data = sse_resp.json()

    assert http_data["name"] == sse_data["name"] == name
    assert http_data["ok"] == sse_data["ok"] is True
    assert http_data["version"] == sse_data["version"]
