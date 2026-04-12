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


def probe_wikijs(base_url: str, api_token: str) -> ProbeResult:
    """Probe Wiki.js via a read-only GraphQL query.

    Sends ``{ pages { list(limit: 1) { id } } }`` and expects a response
    with no ``errors`` field.  Routes through the caller-supplied credentials
    so the probe validates both connectivity AND secret-layer wiring.
    """
    url = f"{base_url.rstrip('/')}/graphql"
    headers = {"Authorization": f"Bearer {api_token}", "Content-Type": "application/json"}
    payload = {"query": "{ pages { list(limit: 1) { id } } }"}
    try:
        resp = httpx.post(url, json=payload, headers=headers, timeout=_TIMEOUT)
    except httpx.ConnectError as exc:
        return ProbeResult(ok=False, detail=f"Connection refused: {exc}")
    except httpx.TimeoutException:
        return ProbeResult(ok=False, detail=f"Timeout after {_TIMEOUT}s connecting to {url}")

    if resp.status_code != 200:
        body_preview = resp.text[:200]
        return ProbeResult(
            ok=False,
            status_code=resp.status_code,
            detail=f"HTTP {resp.status_code}: {body_preview}",
        )

    data = resp.json()
    if "errors" in data:
        error_msg = str(data["errors"])[:200]
        return ProbeResult(ok=False, status_code=200, detail=f"GraphQL errors: {error_msg}")

    return ProbeResult(ok=True, status_code=200)


def probe_aws_sidecar(base_url: str = "http://127.0.0.1:2773") -> ProbeResult:
    """Probe the AWS Secrets Manager sidecar via ``GET /healthz``.

    The sidecar is the official ``aws-secretsmanager-agent`` started alongside
    the MCP container by ``compose.yaml``.  A 200 response confirms the
    sidecar is running and reachable, validating the secrets-layer wiring
    for the ``aws-sidecar`` tier.
    """
    url = f"{base_url.rstrip('/')}/healthz"
    try:
        resp = httpx.get(url, timeout=_TIMEOUT)
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
