"""Unit tests for probe_aws_sidecar (T087)."""

from __future__ import annotations

from unittest.mock import patch

import httpx
import pytest

from agent_power_pack.cpp_init.probes import ProbeResult, probe_aws_sidecar


@pytest.mark.unit
class TestProbeAwsSidecar:
    """Tests for the AWS Secrets Manager sidecar health probe."""

    def test_healthy_sidecar_returns_ok(self) -> None:
        resp = httpx.Response(200, text="ok")
        with patch("agent_power_pack.cpp_init.probes.httpx.get", return_value=resp):
            result = probe_aws_sidecar()
        assert result == ProbeResult(ok=True, status_code=200)

    def test_default_base_url(self) -> None:
        resp = httpx.Response(200, text="ok")
        with patch("agent_power_pack.cpp_init.probes.httpx.get", return_value=resp) as mock_get:
            probe_aws_sidecar()
        mock_get.assert_called_once_with("http://127.0.0.1:2773/healthz", timeout=10.0)

    def test_custom_base_url(self) -> None:
        resp = httpx.Response(200, text="ok")
        with patch("agent_power_pack.cpp_init.probes.httpx.get", return_value=resp) as mock_get:
            probe_aws_sidecar(base_url="http://localhost:9999")
        mock_get.assert_called_once_with("http://localhost:9999/healthz", timeout=10.0)

    def test_trailing_slash_stripped(self) -> None:
        resp = httpx.Response(200, text="ok")
        with patch("agent_power_pack.cpp_init.probes.httpx.get", return_value=resp) as mock_get:
            probe_aws_sidecar(base_url="http://127.0.0.1:2773/")
        mock_get.assert_called_once_with("http://127.0.0.1:2773/healthz", timeout=10.0)

    def test_non_200_status_returns_failure(self) -> None:
        resp = httpx.Response(503, text="Service Unavailable")
        with patch("agent_power_pack.cpp_init.probes.httpx.get", return_value=resp):
            result = probe_aws_sidecar()
        assert result.ok is False
        assert result.status_code == 503
        assert "HTTP 503" in result.detail

    def test_connection_refused(self) -> None:
        with patch(
            "agent_power_pack.cpp_init.probes.httpx.get",
            side_effect=httpx.ConnectError("Connection refused"),
        ):
            result = probe_aws_sidecar()
        assert result.ok is False
        assert result.status_code is None
        assert "Connection refused" in result.detail

    def test_timeout(self) -> None:
        with patch(
            "agent_power_pack.cpp_init.probes.httpx.get",
            side_effect=httpx.TimeoutException("timed out"),
        ):
            result = probe_aws_sidecar()
        assert result.ok is False
        assert result.status_code is None
        assert "Timeout" in result.detail

    def test_body_preview_truncated_at_200_chars(self) -> None:
        long_body = "x" * 500
        resp = httpx.Response(500, text=long_body)
        with patch("agent_power_pack.cpp_init.probes.httpx.get", return_value=resp):
            result = probe_aws_sidecar()
        # "HTTP 500: " is 10 chars, body preview should be 200 chars max
        assert len(result.detail) <= 210
