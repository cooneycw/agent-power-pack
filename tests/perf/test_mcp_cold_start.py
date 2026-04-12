"""Performance test: MCP container cold start to 6 healthy servers in < 15s.

Measures the time from container start to all 6 /healthz endpoints
returning 200 OK.
"""

from __future__ import annotations

import time

import pytest

pytestmark = [pytest.mark.perf]

HTTP_PORTS = [8080, 8081, 8082, 8083, 8084, 8085]
MAX_COLD_START_SECONDS = 15


@pytest.fixture(scope="module")
def mcp_container_timed():
    """Start the MCP container and track startup time."""
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
        start = time.monotonic()
        container.start()
        yield container, start
    except Exception:
        pytest.skip("requires running MCP container / Docker")
    finally:
        try:
            container.stop()
        except Exception:
            pass


def test_cold_start_under_15s(mcp_container_timed) -> None:
    """All 6 servers should respond to /healthz within 15 seconds of container start."""
    import httpx

    container, start_time = mcp_container_timed
    host = container.get_container_host_ip()

    deadline = start_time + MAX_COLD_START_SECONDS
    healthy = set()

    while time.monotonic() < deadline and len(healthy) < len(HTTP_PORTS):
        for port in HTTP_PORTS:
            if port in healthy:
                continue
            try:
                mapped = container.get_exposed_port(port)
                resp = httpx.get(f"http://{host}:{mapped}/healthz", timeout=2)
                if resp.status_code == 200:
                    healthy.add(port)
            except Exception:
                pass
        if len(healthy) < len(HTTP_PORTS):
            time.sleep(0.5)

    elapsed = time.monotonic() - start_time
    assert len(healthy) == len(HTTP_PORTS), (
        f"Only {len(healthy)}/{len(HTTP_PORTS)} servers healthy after {elapsed:.1f}s: "
        f"missing ports {set(HTTP_PORTS) - healthy}"
    )
    assert elapsed < MAX_COLD_START_SECONDS, (
        f"Cold start took {elapsed:.1f}s, exceeding {MAX_COLD_START_SECONDS}s limit"
    )
