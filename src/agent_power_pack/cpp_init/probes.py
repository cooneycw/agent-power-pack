"""Connectivity probes for external tools (research.md §8)."""

from __future__ import annotations

from dataclasses import dataclass

import httpx

_TIMEOUT = 10.0


@dataclass(frozen=True)
class ProbeResult:
    """Outcome of a single connectivity probe."""

    ok: bool
    status_code: int | None = None
    detail: str = ""


def probe_plane(base_url: str, workspace_slug: str, api_token: str) -> ProbeResult:
    """Probe Plane via ``GET /api/v1/workspaces/{slug}/``.

    Expects HTTP 200 from a self-hosted Plane instance (>=v0.19.0).
    Routes through the caller-supplied credentials so the probe validates
    both connectivity AND secret-layer wiring in one shot.
    """
    url = f"{base_url.rstrip('/')}/api/v1/workspaces/{workspace_slug}/"
    headers = {"X-API-Key": api_token}
    try:
        resp = httpx.get(url, headers=headers, timeout=_TIMEOUT)
    except httpx.ConnectError as exc:
        return ProbeResult(ok=False, detail=f"Connection refused: {exc}")
    except httpx.TimeoutException:
        return ProbeResult(ok=False, detail=f"Timeout after {_TIMEOUT}s connecting to {url}")

    if resp.status_code == 200:
        return ProbeResult(ok=True, status_code=200)

    body_preview = resp.text[:200]
    return ProbeResult(
        ok=False,
        status_code=resp.status_code,
        detail=f"HTTP {resp.status_code}: {body_preview}",
    )
