# Implementation Plan: Agent Power Pack Foundation

**Branch**: `001-foundation` | **Date**: 2026-04-11 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/001-foundation/spec.md`

## Summary

Deliver v0.1.0 of agent-power-pack: a universal agentic power pack authored
once in neutral YAML manifests and transpiled at install time to each
first-class runtime (Claude Code, Codex CLI, Gemini CLI, Cursor). The
foundation ships a single multi-transport MCP container hosting
`second-opinion`, `plane`, `wikijs`, `nano-banana`, `playwright`, and
`woodpecker` servers alongside the Rust-based `aws-secretsmanager-agent`
sidecar; an `agents-md:lint` quality gate enforcing AGENTS.md as canonical
with CLAUDE.md/GEMINI.md/.cursorrules as generated outputs; a `project:init`
guided bootstrap that wires Plane and Wiki.js through a tiered secrets
layer; and the `grill-me` (vendored from mattpocock/skills with full
attribution) plus `grill-yourself` skills, with `grill-yourself` auto-firing
as a `/flow:finish` gate when a PR diff exceeds configurable thresholds.

## Technical Context

**Language/Version**: Python 3.11+ for adapters, linter, MCP server host,
  and `project:init`. Rust (pinned via upstream release) for the
  `aws-secretsmanager-agent` sidecar only — consumed as a pre-built binary,
  not rebuilt here.
**Primary Dependencies**: `uv` (workspace + tool install), `ruamel.yaml`
  (YAML parser preserving comments/ordering for manifest round-trips),
  `pydantic` (manifest + lint result schemas), `typer` (CLI layer for
  adapters/linter/project:init), `rich` (terminal UX), `mcp` Python SDK (MCP
  server host), `httpx` (Plane + Wiki.js REST clients), `docker` +
  `docker-compose` v2 (local orchestration).
**Storage**: No application database. Manifests live in `manifests/` as
  YAML files. Secrets traverse dotenv → env-file → AWS Secrets Manager via
  the sidecar's local HTTP endpoint. Grill transcripts land in
  `.specify/grills/<spec-id>.md`. Generated instruction files land at
  repo root.
**Testing**: `pytest` + `pytest-asyncio` for unit/integration; `testcontainers`
  for MCP container smoke tests; golden-file tests for adapter output per
  runtime (shape regression — verifies output structure does not drift);
  Codex CLI smoke tests in `tests/smoke/` (runtime compatibility — verifies
  generated artifacts are consumable by the real `codex` binary); contract
  tests for Plane and Wiki.js MCP tools using recorded fixtures
  (`pytest-recording`/VCR).
**Target Platform**: Linux (Ubuntu 22.04 Jammy inside the MCP container;
  developer machines on Linux or macOS). Windows developers via WSL2 only
  for v0.1.0.
**Project Type**: Multi-component Python monorepo. Components: `adapters/`,
  `manifests/`, `linter/` (under `src/agent_power_pack/linter/`),
  `mcp_container/`, `project_init/`, `vendor/skills/`, `tests/`. Single `uv`
  workspace.
**Performance Goals**:
  - `make install RUNTIME=<x>` completes in <30s on a warm cache.
  - `agents-md:lint` completes in <2s on a typical repo (≤500 lines of
    AGENTS.md, ≤50 Make targets).
  - MCP container cold start to all-six-servers-healthy in <15s.
  - `grill-yourself` produces its transcript in <60s for a 5-file PR.
**Constraints**:
  - Multi-runtime parity per Constitution I — every skill must list all
    first-class runtimes or fail manifest validation.
  - Single-container requirement per Constitution III — no per-server
    containers permitted.
  - Offline-safe linter per Constitution IV — no network calls during
    `agents-md:lint`.
  - Python-only (plus upstream Rust sidecar binary) per Technical Constraints
    in the spec.
**Scale/Scope**:
  - v0.1.0 target catalog: ~40 skills across 11 families (port of existing
    claude/codex-power-pack minus `sequential-thinking` and `docs:pptx`,
    plus new `grill:me`, `grill:yourself`, `issue:*`, `wiki:*`).
  - 4 first-class runtimes at v0.1.0 (Claude Code, Codex CLI) with Gemini
    CLI + Cursor adapters required by v1.0.0 (spec FR-002).
  - 6 MCP servers hosted in 1 container.
  - Single maintainer expected; design for solo ops.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| # | Principle | Status | Notes |
|---|---|---|---|
| I | Multi-Runtime First (NON-NEGOTIABLE) | ✅ PASS | Manifest `runtimes` field + validator rejects any skill that doesn't cover every first-class runtime. v0.1.0 ships Claude + Codex adapters; Gemini + Cursor land before v1.0.0. Gate: `tests/unit/test_manifest_validator.py::test_rejects_partial_runtime_coverage`. |
| II | AGENTS.md is Canonical | ✅ PASS | `agents-md:lint` regenerates CLAUDE.md / GEMINI.md / `.cursorrules` and reverts hand-edits. Generated files carry a `<!-- GENERATED FROM AGENTS.md — DO NOT EDIT -->` header so drift is loud. |
| III | Single MCP Container, Multi-Transport | ✅ PASS | One Dockerfile under `mcp_container/` hosts all six servers via a Python supervisor process; each server binds one stdio/non-streaming HTTP port AND one SSE/streamable port. `aws-secretsmanager-agent` sidecar runs as a second container in the same compose file but is NOT a "per-server" split — it's a cross-cutting secrets dependency. |
| IV | Lint or Lose | ✅ PASS | `agents-md:lint` is deterministic, offline, and wired into `/flow:finish`, `/flow:auto`, and CI merge gates. External-system pings stay out of scope. |
| V | Grill Before You Build | ✅ PASS | `grill-me` is vendored under `vendor/skills/grill-me/` pinned by commit SHA with `ATTRIBUTION.md` at repo root. `grill-yourself` native skill fires via diff-size threshold from `.specify/grill-triggers.yaml`. |

**Gate result**: PASS — no violations, no complexity justifications required.

## Project Structure

### Documentation (this feature)

```text
specs/001-foundation/
├── plan.md              # This file
├── research.md          # Phase 0 output — resolves deferred clarify items
├── data-model.md        # Phase 1 output — entity schemas
├── quickstart.md        # Phase 1 output — first-run walkthrough
├── contracts/           # Phase 1 output — MCP tool + linter + adapter contracts
│   ├── skill-manifest.schema.json
│   ├── agents-md-lint.result.schema.json
│   ├── mcp-tools.second-opinion.md
│   ├── mcp-tools.plane.md
│   ├── mcp-tools.wikijs.md
│   └── runtime-adapter.interface.md
└── tasks.md             # Phase 2 output (/speckit-tasks — NOT created here)
```

### Source Code (repository root)

```text
agent-power-pack/
├── AGENTS.md                          # Canonical project instructions (Principle II)
├── CLAUDE.md                          # GENERATED from AGENTS.md
├── GEMINI.md                          # GENERATED from AGENTS.md
├── .cursorrules                       # GENERATED from AGENTS.md
├── ATTRIBUTION.md                     # Vendored-skill credits (Principle V)
├── Makefile                           # install / mcp-up / mcp-down / verify / lint / test / update-vendored-skills
├── pyproject.toml                     # uv workspace root
├── compose.yaml                       # MCP container + aws-secretsmanager-agent sidecar
│
├── manifests/                         # Neutral YAML skill catalog (Principle I)
│   ├── flow/
│   │   ├── start.yaml
│   │   ├── check.yaml
│   │   └── ...
│   ├── spec/
│   ├── cicd/
│   ├── docs/            (c4 only; no pptx)
│   ├── security/
│   ├── secrets/
│   ├── qa/
│   ├── agents-md/
│   ├── second-opinion/
│   ├── issue/           (Plane-backed, replaces github-issue-*)
│   ├── wiki/            (Wiki.js-backed)
│   ├── project/         (project:init and friends)
│   └── grill/
│       ├── me.yaml      # Wrapper manifest around vendored skill
│       └── yourself.yaml
│
├── vendor/
│   └── skills/
│       └── grill-me/                  # Pinned copy of mattpocock/skills/grill-me @ <SHA>
│           ├── SKILL.md
│           └── VERSION                # Upstream commit SHA
│
├── adapters/                          # Per-runtime transpilers (Principle I)
│   ├── claude/
│   │   └── __init__.py                # manifests → .claude/skills/<name>/SKILL.md
│   ├── codex/
│   │   └── __init__.py                # manifests → .codex/skills/ + ~/.codex/config.toml
│   ├── gemini/                        # Stub for v0.1.0 (lands before v1.0.0)
│   └── cursor/                        # Stub for v0.1.0 (lands before v1.0.0)
│
├── src/
│   └── agent_power_pack/
│       ├── __init__.py
│       ├── cli.py                     # `agent-power-pack` entrypoint (typer)
│       ├── manifest/                  # Pydantic models + YAML loader/validator
│       │   ├── schema.py
│       │   ├── loader.py
│       │   └── validator.py
│       ├── linter/
│       │   ├── agents_md.py           # `agents-md:lint` implementation
│       │   ├── schema_check.py        # (a) required sections present
│       │   ├── repo_check.py          # (b) referenced Make/Docker/CI artifacts exist
│       │   └── generated_check.py     # (c) CLAUDE.md etc. in sync
│       ├── generator/                 # AGENTS.md → per-runtime file generators
│       ├── project_init/                  # Project bootstrap (FR-015/016/016a)
│       │   ├── wizard.py              # Plane + Wiki.js guided config
│       │   └── templates/             # Starter AGENTS.md / Makefile / compose.yaml
│       ├── secrets/                   # Tiered secrets layer (FR-016a)
│       │   ├── dotenv_tier.py
│       │   ├── env_file_tier.py
│       │   └── aws_sidecar_tier.py    # Reads via sidecar local HTTP endpoint
│       ├── grill/
│       │   ├── yourself.py            # Pre-flight self-interrogation
│       │   └── triggers.py            # Diff-size threshold eval (FR-008)
│       └── cicd/
│           └── woodpecker_checklist.py  # FR-017/018 checklist validator
│
├── mcp_container/
│   ├── Dockerfile                     # Base: mcr.microsoft.com/playwright/python:v1.x-jammy
│   ├── supervisor.py                  # Starts + health-checks all six servers
│   ├── servers/
│   │   ├── second_opinion/            # + grill_plan tool (FR-006)
│   │   ├── plane/                     # plane-mcp
│   │   ├── wikijs/                    # wikijs-mcp
│   │   ├── nano_banana/
│   │   ├── playwright_persistent/
│   │   └── woodpecker/
│   └── transports/                    # stdio + HTTP non-streaming + SSE glue
│
└── tests/
    ├── unit/
    │   ├── test_manifest_validator.py
    │   ├── test_agents_md_lint.py
    │   ├── test_grill_triggers.py
    │   ├── test_secrets_tiers.py
    │   └── test_woodpecker_checklist.py
    ├── integration/
    │   ├── test_adapter_claude.py     # Golden-file: manifests → .claude/skills/
    │   ├── test_adapter_codex.py      # Golden-file: manifests → .codex/skills/
    │   └── test_project_init_wizard.py
    └── e2e/
        ├── test_mcp_container_stdio.py   # testcontainers
        ├── test_mcp_container_sse.py     # testcontainers
        └── test_dual_attach.py           # User Story 3 — both runtimes concurrent
```

**Structure Decision**: Multi-component Python monorepo under a single `uv`
workspace. `manifests/` is the source of truth authored by humans;
`adapters/` transpile it per runtime. `src/agent_power_pack/` holds all
installable Python code (linter, generator, project:init, grill, secrets).
`mcp_container/` is the container build context and is NOT installed as a
Python package on developer machines — it's built and run via
`compose.yaml`. `vendor/skills/` is gitignored from `src/` and loaded by the
manifest layer. Tests split by unit / integration / e2e because e2e tests
spin real containers via testcontainers.

## Post-Design Constitution Re-Check

Re-evaluated after Phase 0 (`research.md`) and Phase 1 (`data-model.md`,
`contracts/*`, `quickstart.md`) are complete. No design decision
introduced a new constitutional violation:

| # | Principle | Status | Evidence in Phase 0/1 |
|---|---|---|---|
| I | Multi-Runtime First | ✅ PASS | `contracts/skill-manifest.schema.json` enforces `runtimes` as exactly 4 items; `contracts/runtime-adapter.interface.md` pins a single Python interface for every runtime. |
| II | AGENTS.md Canonical | ✅ PASS | `data-model.md §5–6` models `AgentsMdDocument` + `GeneratedInstructionFile` with source-hash freshness. |
| III | Single MCP Container, Multi-Transport | ✅ PASS | `research.md §3` locks in the in-process supervisor; `contracts/mcp-tools.md` requires every tool on BOTH transports; `quickstart.md §3` brings up one container. |
| IV | Lint or Lose | ✅ PASS | `contracts/agents-md-lint.result.schema.json` codifies the structured result; `data-model.md §7` enforces the `pass/fail` exit contract. |
| V | Grill Before You Build | ✅ PASS | `data-model.md §8–9` models the trigger config + transcript; `research.md §7` pins the vendoring strategy with license-match check. |

**Post-design gate result**: PASS — proceeding to `/speckit-tasks` is
unblocked.

## Complexity Tracking

> No constitutional violations. Table intentionally empty.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — | — | — |
