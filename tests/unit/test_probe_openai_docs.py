"""Unit tests for probe_openai_docs (#148)."""

from __future__ import annotations

from unittest.mock import patch

import httpx
import pytest

from agent_power_pack.cpp_init.probes import ProbeResult, probe_openai_docs


@pytest.mark.unit
class TestProbeOpenaiDocs:
    """Tests for the OpenAI Docs MCP server probe."""

    def test_healthy_endpoint_returns_ok(self) -> None:
        resp = httpx.Response(200, text="ok")
        with patch("agent_power_pack.cpp_init.probes.httpx.get", return_value=resp):
            result = probe_openai_docs("https://docs.example.com/mcp")
        assert result == ProbeResult(ok=True, status_code=200)

    def test_trailing_slash_stripped(self) -> None:
        resp = httpx.Response(200, text="ok")
        with patch("agent_power_pack.cpp_init.probes.httpx.get", return_value=resp) as mock_get:
            probe_openai_docs("https://docs.example.com/mcp/")
        mock_get.assert_called_once_with(
            "https://docs.example.com/mcp",
            timeout=10.0,
            follow_redirects=True,
        )

    def test_non_200_status_returns_failure(self) -> None:
        resp = httpx.Response(404, text="Not Found")
        with patch("agent_power_pack.cpp_init.probes.httpx.get", return_value=resp):
            result = probe_openai_docs("https://docs.example.com/mcp")
        assert result.ok is False
        assert result.status_code == 404
        assert "HTTP 404" in result.detail

    def test_connection_refused(self) -> None:
        with patch(
            "agent_power_pack.cpp_init.probes.httpx.get",
            side_effect=httpx.ConnectError("Connection refused"),
        ):
            result = probe_openai_docs("https://docs.example.com/mcp")
        assert result.ok is False
        assert result.status_code is None
        assert "Connection refused" in result.detail

    def test_timeout(self) -> None:
        with patch(
            "agent_power_pack.cpp_init.probes.httpx.get",
            side_effect=httpx.TimeoutException("timed out"),
        ):
            result = probe_openai_docs("https://docs.example.com/mcp")
        assert result.ok is False
        assert result.status_code is None
        assert "Timeout" in result.detail

    def test_body_preview_truncated_at_200_chars(self) -> None:
        long_body = "x" * 500
        resp = httpx.Response(500, text=long_body)
        with patch("agent_power_pack.cpp_init.probes.httpx.get", return_value=resp):
            result = probe_openai_docs("https://docs.example.com/mcp")
        assert len(result.detail) <= 210
