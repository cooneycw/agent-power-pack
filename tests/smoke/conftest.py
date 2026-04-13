"""Fixtures for Codex CLI smoke tests."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from agent_power_pack.manifest.loader import load_all_manifests
from adapters.codex import CodexAdapter

FIXTURES = Path(__file__).resolve().parent.parent / "integration" / "fixtures" / "manifests"


def _codex_available() -> bool:
    """Return True if the codex CLI is on PATH and responds to --version."""
    codex = shutil.which("codex")
    if codex is None:
        return False
    try:
        result = subprocess.run(
            [codex, "--version"],
            capture_output=True,
            timeout=10,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, OSError):
        return False


requires_codex = pytest.mark.skipif(
    not _codex_available(),
    reason="codex CLI not installed or not responding",
)


@pytest.fixture
def codex_install_dir(tmp_path: Path) -> Path:
    """Install adapter artifacts into a temp directory and return the path."""
    adapter = CodexAdapter()
    manifests = load_all_manifests(FIXTURES)
    adapter.install(manifests, tmp_path)
    return tmp_path


@pytest.fixture
def codex_user_mode_dir(tmp_path: Path) -> Path:
    """Install adapter artifacts in user mode into a fake home and return it."""
    from unittest.mock import patch

    fake_home = tmp_path / "home"
    fake_home.mkdir()

    adapter = CodexAdapter()
    manifests = load_all_manifests(FIXTURES)

    with patch("adapters.codex.Path.home", return_value=fake_home):
        adapter.install(manifests, fake_home, mode="user")

    return fake_home
