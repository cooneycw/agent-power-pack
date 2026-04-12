"""Unit tests for secrets tiers (T083)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import httpx
import pytest

from agent_power_pack.secrets import (
    AwsSidecarTier,
    DotenvTier,
    EnvFileTier,
    HealthStatus,
    NotWritable,
    get_secret,
    resolve_tiers,
    set_secret,
)


@pytest.mark.unit
class TestDotenvTier:
    """Tests for the DotenvTier secrets backend."""

    def test_read_existing_key(self, tmp_path: Path) -> None:
        env_file = tmp_path / ".env"
        env_file.write_text("MY_KEY=my_value\n")
        tier = DotenvTier(dotenv_path=env_file)
        assert tier.get("MY_KEY") == "my_value"

    def test_read_missing_key(self, tmp_path: Path) -> None:
        env_file = tmp_path / ".env"
        env_file.write_text("OTHER_KEY=value\n")
        tier = DotenvTier(dotenv_path=env_file)
        assert tier.get("MISSING") is None

    def test_write_new_key(self, tmp_path: Path) -> None:
        env_file = tmp_path / ".env"
        env_file.write_text("EXISTING=old\n")
        tier = DotenvTier(dotenv_path=env_file)
        tier.set("NEW_KEY", "new_value")
        assert tier.get("NEW_KEY") == "new_value"

    def test_write_creates_file(self, tmp_path: Path) -> None:
        env_file = tmp_path / "subdir" / ".env"
        tier = DotenvTier(dotenv_path=env_file)
        tier.set("CREATED", "yes")
        assert env_file.exists()
        assert tier.get("CREATED") == "yes"

    def test_is_available_with_env(self, tmp_path: Path) -> None:
        env_file = tmp_path / ".env"
        env_file.write_text("KEY=val\n")
        tier = DotenvTier(dotenv_path=env_file)
        assert tier.is_available() is True

    def test_is_available_without_env(self, tmp_path: Path) -> None:
        env_file = tmp_path / ".env"
        tier = DotenvTier(dotenv_path=env_file)
        assert tier.is_available() is False

    def test_health_healthy(self, tmp_path: Path) -> None:
        env_file = tmp_path / ".env"
        env_file.write_text("KEY=val\n")
        tier = DotenvTier(dotenv_path=env_file)
        assert tier.health() == HealthStatus.HEALTHY

    def test_health_unconfigured(self, tmp_path: Path) -> None:
        env_file = tmp_path / ".env"
        tier = DotenvTier(dotenv_path=env_file)
        assert tier.health() == HealthStatus.UNCONFIGURED


@pytest.mark.unit
class TestEnvFileTier:
    """Tests for the EnvFileTier secrets backend."""

    def test_read_existing_key(self, tmp_path: Path) -> None:
        env_file = tmp_path / "env"
        env_file.write_text("DB_HOST=localhost\n")
        tier = EnvFileTier(env_file_path=env_file)
        assert tier.get("DB_HOST") == "localhost"

    def test_read_missing_key(self, tmp_path: Path) -> None:
        env_file = tmp_path / "env"
        env_file.write_text("DB_HOST=localhost\n")
        tier = EnvFileTier(env_file_path=env_file)
        assert tier.get("MISSING") is None

    def test_set_raises_not_writable(self, tmp_path: Path) -> None:
        env_file = tmp_path / "env"
        env_file.write_text("KEY=val\n")
        tier = EnvFileTier(env_file_path=env_file)
        with pytest.raises(NotWritable):
            tier.set("KEY", "new")

    def test_is_available_with_file(self, tmp_path: Path) -> None:
        env_file = tmp_path / "env"
        env_file.write_text("KEY=val\n")
        tier = EnvFileTier(env_file_path=env_file)
        assert tier.is_available() is True

    def test_is_available_without_file(self, tmp_path: Path) -> None:
        env_file = tmp_path / "env"
        tier = EnvFileTier(env_file_path=env_file)
        assert tier.is_available() is False

    def test_health_healthy(self, tmp_path: Path) -> None:
        env_file = tmp_path / "env"
        env_file.write_text("KEY=val\n")
        tier = EnvFileTier(env_file_path=env_file)
        assert tier.health() == HealthStatus.HEALTHY

    def test_health_unconfigured(self, tmp_path: Path) -> None:
        env_file = tmp_path / "env"
        tier = EnvFileTier(env_file_path=env_file)
        assert tier.health() == HealthStatus.UNCONFIGURED

    def test_parses_key_value(self, tmp_path: Path) -> None:
        env_file = tmp_path / "env"
        env_file.write_text("FIRST=one\nSECOND=two\nTHIRD=three\n")
        tier = EnvFileTier(env_file_path=env_file)
        assert tier.get("FIRST") == "one"
        assert tier.get("SECOND") == "two"
        assert tier.get("THIRD") == "three"

    def test_skips_comments_and_empty_lines(self, tmp_path: Path) -> None:
        env_file = tmp_path / "env"
        env_file.write_text("# comment line\n\nKEY=value\n\n# another comment\n")
        tier = EnvFileTier(env_file_path=env_file)
        assert tier.get("KEY") == "value"


@pytest.mark.unit
class TestAwsSidecarTier:
    """Tests for the AwsSidecarTier secrets backend."""

    def test_healthy_sidecar_returns_value(self) -> None:
        health_resp = httpx.Response(200, text="ok")
        get_resp = httpx.Response(
            200,
            text="secret_value",
            request=httpx.Request("GET", "http://127.0.0.1:2773/secretsmanager/get"),
        )

        def mock_get(url: str, **kwargs):
            if "/healthz" in url:
                return health_resp
            return get_resp

        with patch("agent_power_pack.secrets.aws_sidecar_tier.httpx.get", side_effect=mock_get):
            tier = AwsSidecarTier()
            assert tier.get("MY_SECRET") == "secret_value"

    def test_404_returns_none(self) -> None:
        resp = httpx.Response(404, text="not found")
        with patch("agent_power_pack.secrets.aws_sidecar_tier.httpx.get", return_value=resp):
            tier = AwsSidecarTier()
            assert tier.get("MISSING") is None

    def test_connection_error_means_unavailable(self) -> None:
        with patch(
            "agent_power_pack.secrets.aws_sidecar_tier.httpx.get",
            side_effect=httpx.ConnectError("refused"),
        ):
            tier = AwsSidecarTier()
            assert tier.is_available() is False

    def test_set_raises_not_writable(self) -> None:
        tier = AwsSidecarTier()
        with pytest.raises(NotWritable):
            tier.set("KEY", "value")

    def test_health_healthy(self) -> None:
        resp = httpx.Response(200, text="ok")
        with patch("agent_power_pack.secrets.aws_sidecar_tier.httpx.get", return_value=resp):
            tier = AwsSidecarTier()
            assert tier.health() == HealthStatus.HEALTHY

    def test_health_unconfigured_on_connect_error(self) -> None:
        with patch(
            "agent_power_pack.secrets.aws_sidecar_tier.httpx.get",
            side_effect=httpx.ConnectError("refused"),
        ):
            tier = AwsSidecarTier()
            assert tier.health() == HealthStatus.UNCONFIGURED

    def test_health_unhealthy_on_non_200(self) -> None:
        resp = httpx.Response(503, text="down")
        with patch("agent_power_pack.secrets.aws_sidecar_tier.httpx.get", return_value=resp):
            tier = AwsSidecarTier()
            assert tier.health() == HealthStatus.UNHEALTHY


@pytest.mark.unit
class TestTierResolution:
    """Tests for tier resolution and get_secret/set_secret."""

    def test_get_secret_falls_through_tiers(self, tmp_path: Path) -> None:
        """get_secret checks aws-sidecar first, then env-file, then dotenv."""
        dotenv_file = tmp_path / ".env"
        dotenv_file.write_text("FALLBACK_KEY=from_dotenv\n")

        # AWS sidecar unavailable, env-file unavailable, dotenv has the key
        with patch(
            "agent_power_pack.secrets.aws_sidecar_tier.httpx.get",
            side_effect=httpx.ConnectError("refused"),
        ):
            with patch(
                "agent_power_pack.secrets.EnvFileTier.__init__",
                lambda self, **kw: setattr(self, "_path", tmp_path / "nonexistent"),
            ):
                with patch(
                    "agent_power_pack.secrets.DotenvTier.__init__",
                    lambda self, **kw: setattr(self, "_path", dotenv_file),
                ):
                    result = get_secret("FALLBACK_KEY")
        assert result == "from_dotenv"

    def test_set_secret_writes_to_dotenv(self, tmp_path: Path) -> None:
        dotenv_file = tmp_path / ".env"
        dotenv_file.write_text("")

        with patch(
            "agent_power_pack.secrets.DotenvTier.__init__",
            lambda self, **kw: setattr(self, "_path", dotenv_file),
        ):
            set_secret("NEW_KEY", "new_value")

        tier = DotenvTier(dotenv_path=dotenv_file)
        assert tier.get("NEW_KEY") == "new_value"

    def test_resolve_tiers_only_returns_available(self, tmp_path: Path) -> None:
        dotenv_file = tmp_path / ".env"
        dotenv_file.write_text("KEY=val\n")

        # AWS sidecar unavailable, env-file unavailable, dotenv available
        with patch(
            "agent_power_pack.secrets.aws_sidecar_tier.httpx.get",
            side_effect=httpx.ConnectError("refused"),
        ):
            with patch(
                "agent_power_pack.secrets.EnvFileTier.__init__",
                lambda self, **kw: setattr(self, "_path", tmp_path / "nonexistent"),
            ):
                with patch(
                    "agent_power_pack.secrets.DotenvTier.__init__",
                    lambda self, **kw: setattr(self, "_path", dotenv_file),
                ):
                    tiers = resolve_tiers()

        assert len(tiers) == 1
        assert tiers[0].name == "dotenv"
