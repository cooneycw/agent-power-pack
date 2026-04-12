# Phase 0 Research — Agent Power Pack Foundation

Resolves deferred clarifications from `/speckit-clarify` Session 2026-04-11
and pins best-practice choices for technologies named in `plan.md` Technical
Context.

## 1. Plane API version & client strategy

**Decision**: Target Plane **REST API v1** (self-hosted Plane ≥ v0.19.0).
Use `httpx.AsyncClient` with per-workspace base URL from secrets; no
official Python SDK exists as of 2026-04.

**Rationale**: Plane's v1 REST API is stable as of v0.19.0, documented at
`https://developers.plane.so/api-reference/introduction`. The legacy
GraphQL surface is deprecated. Writing a thin typed client around `httpx`
(plus `pydantic` response models) keeps the dependency footprint small and
lets us pin exactly the endpoints we use: `issues`, `cycles`, `modules`,
`workspaces`.

**Alternatives considered**:
- **Community Python SDK (`python-plane-sdk`)** — unmaintained since 2025,
  doesn't cover v1 endpoints we need.
- **GraphQL via `gql`** — deprecated on Plane's side.
- **Plane CLI shell-out** — ties us to a runtime binary and defeats the
  point of `plane-mcp` as a first-class MCP server.

## 2. Wiki.js API version & client strategy

**Decision**: Target Wiki.js **GraphQL API v2** (Wiki.js ≥ 2.5). Use `gql`
with `httpx` transport. Pin GraphQL operations as `.graphql` files under
`mcp_container/servers/wikijs/operations/`.

**Rationale**: Wiki.js exposes ONLY GraphQL for content operations; there
is no REST fallback for page create/update. `gql` + `httpx` gives us
typed responses and offline schema caching. Pinning operations as files
(rather than inline strings) lets us codegen pydantic response models and
lint the queries in CI.

**Alternatives considered**:
- **`python-wikijs-api`** — abandoned 2024; doesn't support Wiki.js 2.5.
- **Direct `httpx.post` with hand-written GraphQL strings** — works but
  loses type safety and schema validation.

## 3. MCP Python SDK choice

**Decision**: `mcp` (the official Anthropic MCP Python SDK) at the latest
stable release. Run it under a custom supervisor (`mcp_container/supervisor.py`)
that starts six server instances in-process using `asyncio` tasks, each
bound to both a stdio-over-HTTP port and an SSE port.

**Rationale**: The official SDK supports stdio, HTTP, and SSE transports
out of the box. An in-process supervisor avoids six separate Python
processes (faster cold start, less memory, simpler health probing) while
still honoring Principle III's "single container, multi-transport" rule.

**Alternatives considered**:
- **Six subprocesses managed by `supervisord`** — more memory, slower
  boot, and the transport config duplicates per server.
- **FastMCP** — third-party wrapper; adds a dependency without buying
  features we need for six small servers.

## 4. Performance targets (resolves Clarify "Deferred — Performance")

**Decision**: Pin targets and codify as pytest markers that fail CI if
exceeded:

| Operation | Target | How measured |
|---|---|---|
| `make install RUNTIME=<x>` (warm cache) | < 30 s | `tests/perf/test_install_time.py` |
| `agents-md:lint` on a 500-line AGENTS.md w/ 50 make targets | < 2 s | `tests/perf/test_lint_time.py` |
| MCP container cold start → 6 servers healthy | < 15 s | `tests/e2e/test_mcp_container_stdio.py::test_cold_start_budget` |
| `grill-yourself` on a 5-file / 200-line PR | < 60 s | `tests/perf/test_grill_yourself.py` |
| `app:init` end-to-end with Plane + Wiki.js skipped | < 10 s | `tests/integration/test_app_init_wizard.py` |

**Rationale**: These numbers come from the equivalent flows in
claude-power-pack (install ~15s, lint ~800ms) plus headroom for the
multi-runtime transpile step. They're chosen to be comfortably achievable
on a typical laptop but tight enough to catch regressions.

**Alternatives considered**: looser targets (60s install, 5s lint) —
rejected because the existing power-packs already hit the recommended
numbers, so loosening would permit drift.

## 5. Observability (resolves Clarify "Deferred — Observability")

**Decision**: Structured JSON logs via `structlog` for every Python
component. One log line per significant action with these fields: `ts`,
`level`, `component`, `event`, `duration_ms`, `error`. MCP servers emit
tool-call logs with `tool`, `client_runtime`, `request_id`. No metrics
backend for v0.1.0; logs are sufficient for solo ops. No tracing.

**Rationale**: `structlog` is the standard structured-logging library in
modern Python and integrates cleanly with stdlib `logging`. JSON to stdout
lets Docker / Woodpecker slurp it without agents. Metrics and tracing are
deliberately deferred — we'd be adding infra with no reader.

**Alternatives considered**:
- **OpenTelemetry + OTLP exporter** — right answer long-term but adds a
  collector dep; defer to v0.2.
- **Plain `logging` with a custom formatter** — `structlog` is a trivial
  upgrade and gives context binding for free.

## 6. Runtime adapter interface

**Decision**: Each adapter is a Python module exposing a single function
`install(manifests: list[SkillManifest], target_dir: Path, *, mode: Literal["project", "user"]) -> InstallReport`. Adapters import `agent_power_pack.manifest.schema` for the input model and return a dataclass listing
files written, files skipped, and validation errors. Adapters live under
`adapters/<runtime>/` and are discovered by the CLI via an entry point
group `agent_power_pack.adapters`.

**Rationale**: A single function signature lets us swap runtimes behind
`make install RUNTIME=<x>` with a one-line dispatch. Entry points let
third parties ship their own adapter as a pip package without forking.

**Alternatives considered**:
- **Abstract base class** — Python duck typing + `Protocol` from `typing`
  is lighter and more Pythonic.
- **Jinja templates per runtime** — sufficient for simple cases but
  breaks down for Codex's `~/.codex/config.toml` merge and for
  `.cursorrules` generation. Code-based adapters are clearer.

## 7. Vendored grill-me skill pinning strategy

**Decision**: Vendor `grill-me` as a git subtree-like copy at
`vendor/skills/grill-me/` with a `VERSION` file containing the upstream
commit SHA from `mattpocock/skills`. `make update-vendored-skills` runs a
script that:
1. Clones `mattpocock/skills` at `HEAD` into a temp dir.
2. Copies `grill-me/` into `vendor/skills/grill-me/`.
3. Writes the new SHA to `VERSION`.
4. Verifies the LICENSE file still matches the recorded license in
   `ATTRIBUTION.md`; fails if the license changed.
5. Leaves the change as a working tree diff for human review.

**Rationale**: Subtree-style vendoring is boring, works offline, and
requires no git subtree machinery or submodule hazards. The license-match
check catches upstream license changes before they land.

**Alternatives considered**:
- **Git submodule** — forces every clone to init the submodule and
  couples CI setup.
- **pip-installed package** — mattpocock publishes skills as repo
  directories, not PyPI packages.
- **Script that downloads on install** — network dependency at install
  time breaks offline developer machines.

## 8. `app:init` connectivity-check design

**Decision**: For each configured external tool, `app:init` makes ONE
idempotent read-only call through the same secrets tier the runtime will
use:
- **Plane**: `GET /api/v1/workspaces/{slug}/` — expected 200; any other
  response reports failure with status + first 200 bytes of body.
- **Wiki.js**: GraphQL query `{ pages { list(limit: 1) { id } } }` —
  expected no `errors` field; otherwise failure.
- **AWS secrets sidecar**: `GET http://127.0.0.1:2773/healthz` on the
  sidecar's local health port (if sidecar tier active).

Connectivity failures are recoverable: the wizard offers retry, edit
credentials, or skip. Skip paths are recorded in the wizard's final report
and surfaced in `app:init --status`.

**Rationale**: Single read-only probes minimize side effects during
onboarding. Routing through the same tier as runtime use verifies BOTH
the credentials AND the secrets layer wiring in one shot.

**Alternatives considered**:
- **Write a dummy issue/page** — confirms write perms but leaves
  detritus; rejected.
- **Skip connectivity check entirely** — fails User Story 6 acceptance
  scenario 1.

## 9. Woodpecker checklist validator (FR-017/018)

**Decision**: Implement as a standalone Python module
(`src/agent_power_pack/cicd/woodpecker_checklist.py`) that parses
`.woodpecker.yml` with `ruamel.yaml` and evaluates each rule from the
`cooneycw/woodpecker-baseline` findings as a pure function. Rules are
registered in a dict keyed by rule ID so the checklist doubles as
documentation. Two run modes:
- **Interactive** (`cicd:woodpecker-checklist`): walks the user through
  each rule with pass/fail/waive/explain.
- **Validator** (`cicd:init`): runs all rules non-interactively, emits a
  JSON report, exits non-zero on any non-waivable failure.

Rules at v0.1.0 are exactly the ones enumerated in FR-017. Each rule has
a fixture file under `tests/unit/fixtures/woodpecker/` with a known-bad
and known-good example.

**Rationale**: Pure-function rules are trivially testable; the dict
registry keeps adding rules cheap; the dual-mode surface maps directly to
FR-017 (checklist) and FR-018 (`cicd:init` gate).

**Alternatives considered**:
- **Shell script with `yq`** — harder to test, mixes parsing with rule
  logic, and duplicates the Python pipeline we already need.
- **Open-policy-agent (Rego)** — overkill for ≤15 rules and adds a
  non-Python dependency.

## Summary Table

| Area | Decision | Pinned In |
|---|---|---|
| Plane client | `httpx` + hand-written v1 REST client | `mcp_container/servers/plane/` |
| Wiki.js client | `gql` + `httpx` GraphQL v2, `.graphql` files | `mcp_container/servers/wikijs/` |
| MCP SDK | Official `mcp` Python SDK, in-process supervisor | `mcp_container/supervisor.py` |
| Performance | 30s install / 2s lint / 15s cold start / 60s grill / 10s app:init | `tests/perf/` |
| Observability | `structlog` JSON to stdout, no metrics, no tracing (v0.1.0) | Every component |
| Adapter interface | `install(manifests, target_dir, mode)` via entry points | `adapters/<runtime>/` |
| Vendored skills | Subtree copy + VERSION file + license-match check | `vendor/skills/` + `make update-vendored-skills` |
| `app:init` probe | Read-only call through runtime tier | `app_init/wizard.py` |
| Woodpecker checklist | Pure-function rules in a dict registry, dual mode | `cicd/woodpecker_checklist.py` |

All NEEDS CLARIFICATION items resolved.
