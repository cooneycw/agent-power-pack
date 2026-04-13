---

description: "Task list for the Agent Power Pack Foundation feature"
---

# Tasks: Agent Power Pack Foundation

**Input**: Design documents from `/specs/001-foundation/`
**Prerequisites**: `plan.md` (required), `spec.md` (required), `research.md`, `data-model.md`, `contracts/`

**Tests**: Included — the spec has concrete success criteria, acceptance scenarios, and performance targets that require automated verification.

**Organization**: Tasks are grouped by user story (US1–US6) to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to (US1–US6)
- Include exact file paths in descriptions

## Path Conventions

Multi-component Python monorepo under a single `uv` workspace per `plan.md`. Key roots:

- `src/agent_power_pack/` — installable Python package (linter, generator, project:init, grill, secrets, cicd)
- `adapters/<runtime>/` — per-runtime transpilers
- `manifests/<family>/*.yaml` — neutral skill catalog
- `mcp_container/` — single-container MCP build context
- `vendor/skills/` — pinned third-party skills
- `tests/{unit,integration,e2e,perf}/` — split by test style

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Stand up the uv workspace, dev tooling, and repo-level docs.

- [ ] T001 Create top-level directory skeleton (`adapters/`, `manifests/`, `src/agent_power_pack/`, `mcp_container/`, `vendor/skills/`, `tests/{unit,integration,e2e,perf}/`) per `plan.md` Structure.
- [ ] T002 Initialize `uv` workspace at repo root in `pyproject.toml` with Python 3.11+ requirement and workspace members for `src/agent_power_pack`, `adapters/claude`, `adapters/codex`, `adapters/gemini`, `adapters/cursor`, `mcp_container`.
- [ ] T003 [P] Add core runtime deps (`pydantic`, `ruamel.yaml`, `typer`, `rich`, `structlog`, `httpx`, `mcp`, `gql`, `docker`) to `pyproject.toml` and lock via `uv lock`.
- [ ] T004 [P] Add dev deps (`pytest`, `pytest-asyncio`, `pytest-recording`, `testcontainers`, `ruff`, `mypy`) to `[dependency-groups.dev]` in `pyproject.toml`.
- [ ] T005 [P] Configure `ruff` + `mypy` in `pyproject.toml` (line length 100, strict mypy for `src/agent_power_pack/`).
- [ ] T006 [P] Configure `pytest` in `pyproject.toml` with markers `unit`, `integration`, `e2e`, `perf` and asyncio mode `auto`.
- [ ] T007 Scaffold top-level `Makefile` with empty targets: `install`, `mcp-up`, `mcp-down`, `verify`, `lint`, `test`, `update-vendored-skills`, `secrets-sidecar-up` (bodies added by later tasks).
- [ ] T008 [P] Create `LICENSE` (MIT) and `ATTRIBUTION.md` skeleton at repo root with the vendoring-credit template from `research.md §7`.
- [ ] T009 [P] Create `.env.example` at repo root documenting the secrets keys each MCP server reads (OpenAI, Anthropic, Gemini, Plane token, Wiki.js token).
- [ ] T010 [P] Create `.gitignore` covering `.venv/`, `__pycache__/`, `.pytest_cache/`, `.mypy_cache/`, `.env`, `.specify/grills/`, generated golden-file output dirs.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core schemas, validators, and shared infrastructure that every user story depends on.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [ ] T011 Implement `Runtime` enum in `src/agent_power_pack/manifest/schema.py` with the four canonical values from `data-model.md §2`.
- [ ] T012 Implement `Attribution`, `McpToolRef`, and `SkillManifest` pydantic models in `src/agent_power_pack/manifest/schema.py` per `data-model.md §1,§3,§4` and `contracts/skill-manifest.schema.json`.
- [ ] T013 Implement YAML loader in `src/agent_power_pack/manifest/loader.py` using `ruamel.yaml` round-trip mode preserving comments and ordering.
- [ ] T014 Implement `SkillManifest` validator in `src/agent_power_pack/manifest/validator.py` enforcing Principle I (runtimes must equal the full canonical set) and cross-checking vendored-manifest attribution against `vendor/skills/<name>/VERSION`.
- [ ] T015 [P] Unit tests in `tests/unit/test_manifest_validator.py` covering: valid manifest, partial-runtime rejection, vendored-manifest SHA mismatch, illegal `family`, illegal `mcp_tools.server` — must exercise every validation branch from `data-model.md §1`.
- [ ] T016 [P] Unit tests in `tests/unit/test_manifest_loader.py` for YAML round-trip fidelity (comments preserved, field order stable).
- [ ] T017 Configure `structlog` in `src/agent_power_pack/logging.py` per `research.md §5` (JSON to stdout, bound fields `component`, `event`, `duration_ms`, `error`).
- [ ] T018 Implement the `agent-power-pack` CLI entrypoint in `src/agent_power_pack/cli.py` using `typer` with empty subcommands for `install`, `lint`, `generate`, `init`, `flow`, `grill` (bodies added in story phases).
- [ ] T019 Register the `agent_power_pack.adapters` entry-point group in `pyproject.toml` with the four adapter module paths from `contracts/runtime-adapter.interface.md`.
- [ ] T020 Implement `adapters/report.py` with the `InstallReport` dataclass from `contracts/runtime-adapter.interface.md`.

**Checkpoint**: Foundation ready — user story implementation can now begin in parallel where dependencies allow.

---

## Phase 3: User Story 1 — Bootstrap on any runtime (Priority: P1) 🎯 MVP

**Goal**: A developer can run `make install RUNTIME=<claude|codex>` on a fresh repo and get a working skill catalog in the runtime's native layout, with no manual editing. Gemini and Cursor adapters are stubs that fail fast.

**Independent Test**: `make install RUNTIME=claude` and `make install RUNTIME=codex` against a fixed set of 3 manifests each produce a file tree matching the golden fixtures byte-for-byte; a second invocation produces no diff. `make install-codex-user` writes managed `mcp_servers` entries to `~/.codex/config.toml` without disturbing non-agent-power-pack content.

- [ ] T021 [P] [US1] Create three fixture manifests under `tests/integration/fixtures/manifests/` (one minimal, one with `mcp_tools`, one with `attribution`) covering the edge cases listed in `contracts/runtime-adapter.interface.md`.
- [ ] T022 [P] [US1] Implement the Claude adapter in `adapters/claude/__init__.py` per `contracts/runtime-adapter.interface.md` — writes `target_dir/.claude/skills/<name>/SKILL.md` with YAML frontmatter, project + user modes.
- [ ] T023 [P] [US1] Implement the Codex adapter in `adapters/codex/__init__.py` — writes `target_dir/.codex/skills/<name>/agents/openai.yaml`, `target_dir/.codex/prompts/<family>/<name>.md`, and (user mode only) three-way merge into `~/.codex/config.toml`.
- [ ] T024 [P] [US1] Implement Gemini adapter stub in `adapters/gemini/__init__.py` — raises `AdapterNotImplemented("gemini-cli adapter lands before v1.0.0")` with a link to spec FR-002.
- [ ] T025 [P] [US1] Implement Cursor adapter stub in `adapters/cursor/__init__.py` — same pattern as the Gemini stub.
- [ ] T026 [US1] Wire the `agent-power-pack install --runtime <name>` subcommand in `src/agent_power_pack/cli.py` to dispatch via the `agent_power_pack.adapters` entry-point group, returning the `InstallReport` as human table or JSON.
- [ ] T027 [US1] Implement `make install RUNTIME=<x>` in the top-level `Makefile` to shell out to the CLI with absolute paths; fail with `Unknown runtime` on invalid input.
- [ ] T028 [US1] Create golden-file fixtures under `tests/integration/golden/claude/` and `tests/integration/golden/codex/` matching the three fixture manifests.
- [ ] T029 [P] [US1] Integration tests in `tests/integration/test_adapter_claude.py`: load fixtures, install to tmpdir, assert file tree matches golden, assert `InstallReport.files_written` matches, assert idempotence on rerun.
- [ ] T030 [P] [US1] Integration tests in `tests/integration/test_adapter_codex.py` mirroring the claude test, plus the `~/.codex/config.toml` merge case.
- [ ] T031 [P] [US1] Unit test in `tests/unit/test_adapter_stubs.py` asserting the Gemini and Cursor stubs raise `AdapterNotImplemented`.
- [ ] T032 [P] [US1] Performance test in `tests/perf/test_install_time.py` asserting `make install RUNTIME=claude` completes in < 30s on warm cache (spec perf target).

**Checkpoint**: User Story 1 complete — the multi-runtime install story delivers an MVP. A developer can already use agent-power-pack skills in Claude Code and Codex CLI, even though the AGENTS.md linter and MCP container are still stubs.

### Phase 3b: Codex smoke tests — runtime compatibility verification (Issue #144)

- [ ] T046 [US1] Implement Codex smoke test harness in `tests/smoke/test_codex_smoke.py` with Tier 1 (structure validation) and Tier 2 (CLI verification) tests per updated runtime-adapter contract.
- [ ] T047 [P] [US1] Wire `codex-smoke` step into `.woodpecker.yml` running `pytest -m codex_smoke` after the `test` step, with codex CLI installed via npm.
- [ ] T048 [US1] Update testing methodology docs (`runtime-adapter.interface.md`, `plan.md`) to distinguish "golden output correctness" (shape regression) from "runtime compatibility" (smoke tests).

**Gate**: Phase 3 is not considered complete without at least Tier 1 smoke tests passing in CI.

---

## Phase 4: User Story 2 — AGENTS.md canonical + lint gate (Priority: P1)

**Goal**: `AGENTS.md` is the single source of truth. The linter enforces required sections, cross-checks every referenced Make target / command / Docker service / CI file, regenerates `CLAUDE.md` / `GEMINI.md` / `.cursorrules`, and reverts hand-edits to generated files.

**Independent Test**: Edit `AGENTS.md` to reference a nonexistent Make target; `agent-power-pack lint agents-md` exits non-zero and names the missing target. Add the target and the lint passes.

- [ ] T033 [US2] Implement `AgentsMdDocument` loader in `src/agent_power_pack/linter/document.py` per `data-model.md §5`, extracting referenced make targets, commands, docker services, and CI file paths from prose and code blocks.
- [ ] T034 [P] [US2] Implement `schema_check.py` in `src/agent_power_pack/linter/schema_check.py` enforcing the six required sections from `data-model.md §5`.
- [ ] T035 [P] [US2] Implement `repo_check.py` in `src/agent_power_pack/linter/repo_check.py` verifying every referenced Make target, command, Docker service, and CI file actually exists in the repo (spec FR-004(b)).
- [ ] T036 [P] [US2] Implement `generated_check.py` in `src/agent_power_pack/linter/generated_check.py` enforcing `CLAUDE.md` / `GEMINI.md` / `.cursorrules` freshness via `AgentsMdDocument.content_hash` per `data-model.md §6`.
- [ ] T037 [US2] Implement `LintResult` and `LintCheck` pydantic models in `src/agent_power_pack/linter/result.py` matching `contracts/agents-md-lint.result.schema.json`.
- [ ] T038 [US2] Implement `agents-md:lint` top-level orchestrator in `src/agent_power_pack/linter/agents_md.py` running all three checks and composing a `LintResult` with `duration_ms`.
- [ ] T039 [US2] Implement generator in `src/agent_power_pack/generator/instruction_files.py`: AGENTS.md → CLAUDE.md / GEMINI.md / .cursorrules with the canonical `<!-- GENERATED FROM AGENTS.md — DO NOT EDIT -->` header.
- [ ] T040 [US2] Implement hand-edit revert logic in `src/agent_power_pack/generator/revert.py`: on detected drift, revert the generated file and emit a `LintCheck` with `status: fail` and subject = the path.
- [ ] T041 [US2] Wire `agent-power-pack lint agents-md` subcommand in `src/agent_power_pack/cli.py` with `--json` flag honoring the schema.
- [ ] T042 [US2] Wire `agent-power-pack generate` subcommand that regenerates all instruction files from AGENTS.md.
- [ ] T043 [US2] Create the canonical `AGENTS.md` at repo root covering the six required sections with references to targets/commands that actually exist.
- [ ] T044 [P] [US2] Unit tests in `tests/unit/test_agents_md_lint.py` covering every rule ID (missing section, missing make target, stale generated file, hand-edit revert) — one test per rule per spec SC-003.
- [ ] T045 [P] [US2] Performance test in `tests/perf/test_lint_time.py` asserting a 500-line AGENTS.md + 50 targets lints in < 2s.

**Checkpoint**: User Story 2 complete — AGENTS.md is locked in as canonical and the linter is a real gate.

---

## Phase 5: User Story 3 — Single multi-transport MCP container (Priority: P1)

**Goal**: One Docker image hosts all six MCP servers. Each server is reachable on BOTH a stdio / non-streaming HTTP port AND an SSE / streamable port, so Claude Code and Codex CLI can attach concurrently.

**Independent Test**: `make mcp-up` then `curl /healthz` on each server's port returns healthy; a Claude Code session and a Codex CLI session call `second-opinion.review` concurrently and both succeed with identical results.

- [ ] T046 [US3] Write `mcp_container/Dockerfile` using `mcr.microsoft.com/playwright/python:v1.x-jammy` as base, installing the project via `uv sync --frozen` and starting `supervisor.py`.
- [ ] T047 [US3] Write `compose.yaml` at repo root defining the `mcp` service (the container) plus the `secrets-sidecar` service using the official `aws/aws-secretsmanager-agent` image, sharing a bridge network.
- [ ] T048 [US3] Implement `mcp_container/supervisor.py` starting all six MCP servers as `asyncio` tasks in a single process, per `research.md §3`.
- [ ] T049 [US3] Implement dual-transport routing in `mcp_container/transports/` — stdio + non-streaming HTTP on ports 8080–8085, streamable HTTP (with SSE compatibility) on ports 9100–9105, one server per port pair.
- [ ] T050 [P] [US3] Implement `second_opinion` server under `mcp_container/servers/second_opinion/` porting the claude-power-pack implementation plus the new `grill_plan` tool per `contracts/mcp-tools.md`.
- [ ] T051 [P] [US3] Implement `plane` server under `mcp_container/servers/plane/` using `httpx` REST v1 client with tools `list_workspaces`, `create_issue`, `update_issue`, `list_issues`, `close_issue`, `list_cycles`.
- [ ] T052 [P] [US3] Implement `wikijs` server under `mcp_container/servers/wikijs/` using `gql` + `httpx` GraphQL v2 client with `.graphql` operation files, plus the new `publish_c4` tool.
- [ ] T053 [P] [US3] Port `nano_banana` server under `mcp_container/servers/nano_banana/` — diagram tools only; `pptx` tool is NOT carried over per spec FR-011.
- [ ] T054 [P] [US3] Port `playwright_persistent` server under `mcp_container/servers/playwright_persistent/` unchanged from source power-packs.
- [ ] T055 [P] [US3] Port `woodpecker` server under `mcp_container/servers/woodpecker/` unchanged (9 tools from `contracts/mcp-tools.md`).
- [ ] T056 [US3] Implement `/healthz` endpoint on every server returning `{ ok: true, name, version }`.
- [ ] T057 [US3] Implement `make mcp-up`, `make mcp-down`, `make mcp-health` targets in `Makefile` shelling out to `docker compose`.
- [ ] T058 [US3] Implement `make secrets-sidecar-up` to start only the sidecar service (for dev use without the full MCP container).
- [ ] T059 [P] [US3] E2E test in `tests/e2e/test_mcp_container_stdio.py` using `testcontainers` to verify stdio transport against a fixture call.
- [ ] T060 [P] [US3] E2E test in `tests/e2e/test_mcp_container_sse.py` verifying SSE transport.
- [ ] T061 [US3] E2E test in `tests/e2e/test_dual_attach.py` (spec User Story 3) verifying both transports return identical results when called concurrently.
- [ ] T062 [P] [US3] Performance test in `tests/perf/test_mcp_cold_start.py` asserting cold start → 6 servers healthy in < 15s.

**Checkpoint**: User Story 3 complete — a single container serves both runtimes with all six servers.

---

## Phase 6: User Story 4 — `grill-yourself` as a flow gate (Priority: P2)

**Goal**: `grill-yourself` fires automatically before `flow:finish` when the pending diff exceeds configurable thresholds (default > 200 lines OR > 5 files), and attaches its transcript to the PR. Manual invocation also works.

**Independent Test**: Create a PR with a 300-line diff; `agent-power-pack flow finish` triggers `grill-yourself` and writes a transcript under `.specify/grills/<timestamp>.md`. A trailer `grill-yourself: skip` on the HEAD commit suppresses it.

- [ ] T063 [P] [US4] Implement `GrillTriggerConfig` pydantic model + YAML loader in `src/agent_power_pack/grill/config.py` per `data-model.md §8`.
- [ ] T064 [P] [US4] Create default `.specify/grill-triggers.yaml` with `max_lines: 200` and `max_files: 5`.
- [ ] T065 [US4] Implement `should_grill(diff)` in `src/agent_power_pack/grill/triggers.py` evaluating thresholds against `git diff --numstat` output and honoring HEAD commit message trailers `grill-yourself: force|skip`.
- [ ] T066 [P] [US4] Implement `GrillTranscript` model + markdown renderer in `src/agent_power_pack/grill/transcript.py` per `data-model.md §9`.
- [ ] T067 [US4] Implement `grill-yourself` command in `src/agent_power_pack/grill/yourself.py`: generate ≥5 pre-flight questions, answer them, render as `GrillTranscript`, save under `.specify/grills/<spec-id-or-timestamp>.md`.
- [ ] T068 [US4] Wire `agent-power-pack grill yourself [plan]` subcommand in `src/agent_power_pack/cli.py`.
- [ ] T069 [US4] Wire `agent-power-pack flow finish` subcommand to call `should_grill()` and run `grill-yourself` automatically when triggered, attaching transcript to the PR description via `gh pr edit`.
- [ ] T070 [P] [US4] Unit tests in `tests/unit/test_grill_triggers.py` covering threshold boundaries, trailer override both directions, `exclude_globs`, empty diff.
- [ ] T071 [P] [US4] Performance test in `tests/perf/test_grill_yourself.py` asserting grill-yourself on a 5-file / 200-line PR completes in < 60s.

**Checkpoint**: User Story 4 complete — `grill-yourself` is a real flow gate.

---

## Phase 7: User Story 5 — `grill-me` vendored with attribution (Priority: P2)

**Goal**: `grill-me` is vendored from `mattpocock/skills` pinned by SHA, attribution preserved in the skill manifest header and `ATTRIBUTION.md`.

**Independent Test**: `grill:me` triggers one-question-at-a-time interactive mode; the installed SKILL file credits the upstream URL; `make update-vendored-skills` updates the pinned SHA.

- [ ] T072 [US5] Vendor the `grill-me` skill from `mattpocock/skills` into `vendor/skills/grill-me/` at a pinned SHA; create `vendor/skills/grill-me/VERSION` containing the SHA.
- [ ] T073 [US5] Create `manifests/grill/me.yaml` wrapper manifest around the vendored skill, with `attribution.source`, `attribution.commit_sha` (matching `VERSION`), and `attribution.license`.
- [ ] T074 [US5] Create `manifests/grill/yourself.yaml` native manifest pointing the prompt at `src/agent_power_pack/grill/yourself.py`.
- [ ] T075 [US5] Implement `scripts/update_vendored_skills.py` performing the 5 steps from `research.md §7` (clone, copy, update VERSION, license match, leave diff for review).
- [ ] T076 [US5] Wire `make update-vendored-skills` in `Makefile` to call the script.
- [ ] T077 [US5] Populate `ATTRIBUTION.md` at repo root listing `grill-me` with upstream URL, commit SHA, and license.
- [ ] T078 [P] [US5] Unit tests in `tests/unit/test_vendoring.py` covering SHA mismatch detection and license-match failure.

**Checkpoint**: User Story 5 complete — grill-me is installed and properly credited.

---

## Phase 8: User Story 6 — Plane + Wiki.js defaults, `project:init` guided wizard (Priority: P2)

**Goal**: `project:init` bootstraps a new project end-to-end, including a guided Plane + Wiki.js configuration through the tiered secrets layer. `issue:*` defaults to Plane, `docs:c4` publishes to Wiki.js, `docs:pptx` does not exist.

**Independent Test**: Run `project:init` in a fresh directory with valid Plane/Wiki.js creds; both connectivity checks pass and `AGENTS.md` gains an `External Systems` section.

- [ ] T079 [US6] Implement the `SecretTier` Protocol and `DotenvTier` in `src/agent_power_pack/secrets/dotenv_tier.py` per `data-model.md §10`.
- [ ] T080 [P] [US6] Implement `EnvFileTier` in `src/agent_power_pack/secrets/env_file_tier.py`.
- [ ] T081 [P] [US6] Implement `AwsSidecarTier` in `src/agent_power_pack/secrets/aws_sidecar_tier.py` reading via the sidecar's local HTTP endpoint (`http://127.0.0.1:2773/`).
- [ ] T082 [US6] Implement tier-resolution in `src/agent_power_pack/secrets/__init__.py` (order: aws-sidecar → env-file → dotenv; first-available wins on read; writes go to dotenv by default).
- [ ] T083 [P] [US6] Unit tests in `tests/unit/test_secrets_tiers.py` covering read fallthrough, write routing, sidecar unavailability.
- [ ] T084 [US6] Implement `project:init` wizard in `src/agent_power_pack/project_init/wizard.py` scaffolding AGENTS.md + Makefile + compose.yaml from `src/agent_power_pack/project_init/templates/`, then running the Plane + Wiki.js guided config.
- [ ] T085 [US6] Implement the Plane connectivity probe in `src/agent_power_pack/project_init/probes.py` (`GET /api/v1/workspaces/{slug}/` expecting 200) per `research.md §8`.
- [ ] T086 [US6] Implement the Wiki.js connectivity probe (GraphQL `{ pages { list(limit: 1) { id } } }`) per `research.md §8`.
- [ ] T087 [US6] Implement the AWS sidecar health probe (`GET http://127.0.0.1:2773/healthz`) per `research.md §8`.
- [ ] T088 [US6] Implement the "External Systems" section writer in `src/agent_power_pack/project_init/agents_md_update.py` adding a generated section to AGENTS.md with configured endpoints.
- [ ] T089 [US6] Wire `agent-power-pack init` and `agent-power-pack init --reconfigure {plane|wikijs}` in `src/agent_power_pack/cli.py`.
- [ ] T090 [P] [US6] Author `manifests/issue/*.yaml` for `issue:create`, `issue:update`, `issue:list`, `issue:close`, `issue:help` using `plane-mcp` tools.
- [ ] T091 [P] [US6] Author `manifests/wiki/*.yaml` for `wiki:create-page`, `wiki:update-page`, `wiki:search` using `wikijs-mcp` tools.
- [ ] T092 [P] [US6] Author `manifests/docs/c4.yaml` using `wikijs-mcp.publish_c4`. Do NOT create `manifests/docs/pptx.yaml` (spec FR-011).
- [ ] T093 [P] [US6] Integration test in `tests/integration/test_project_init_wizard.py` covering the happy path and both `--skip` paths.
- [ ] T094 [P] [US6] Performance test in `tests/perf/test_project_init.py` asserting project:init (Plane + Wiki.js skipped) completes in < 10s.

**Checkpoint**: User Story 6 complete — new projects bootstrap with Plane/Wiki.js configured in a single run.

---

## Phase 9: Woodpecker Checklist (FR-017 / FR-018)

**Purpose**: Deliver the learned-findings checklist derived from `cooneycw/woodpecker-baseline`. Cross-cuts US3 and CI/CD setup.

- [ ] T095 Implement `WoodpeckerCheckResult` + `WoodpeckerRuleResult` models in `src/agent_power_pack/cicd/woodpecker_checklist_models.py` per `data-model.md §11`.
- [ ] T096 Implement the rule registry in `src/agent_power_pack/cicd/woodpecker_checklist.py` as a dict keyed by rule ID, with pure-function evaluators for each rule from spec FR-017 (pinned image tags, safe.directory, no-unjustified-failure-ignore, stale-commit guard, concurrent-deploy lock, two-phase readiness with proxy buffer, secrets-readable-first-step, explicit when+depends_on, required agent labels, pre-merge non-prod test).
- [ ] T097 [P] Create test fixtures under `tests/unit/fixtures/woodpecker/` — one known-bad and one known-good `.woodpecker.yml` per rule.
- [ ] T098 [P] Unit tests in `tests/unit/test_woodpecker_checklist.py` — one parametrized test per rule asserting bad fixtures fail and good fixtures pass (spec SC-009).
- [ ] T099 Implement interactive + validator run modes in `src/agent_power_pack/cicd/woodpecker_checklist.py` (spec FR-017).
- [ ] T100 [P] Author `manifests/cicd/woodpecker-checklist.yaml` skill manifest with both interactive and validator triggers.
- [ ] T101 Wire `cicd:init` to invoke the checklist in validator mode against any generated `.woodpecker.yml` and refuse to finalize on non-waivable failures (spec FR-018).

---

## Phase 10: Port the rest of the skill catalog

**Purpose**: Author the remaining neutral YAML manifests for the flow / spec / cicd / security / secrets / qa / agents-md / second-opinion / project families. One task per family (each is a batch of manifest files).

- [ ] T102 [P] Author `manifests/flow/*.yaml` for `flow:start`, `flow:check`, `flow:finish`, `flow:auto`, `flow:deploy`, `flow:merge`, `flow:sync`, `flow:cleanup`, `flow:status`, `flow:doctor`, adapted to use `plane-mcp` issues.
- [ ] T103 [P] Author `manifests/spec/*.yaml` for `spec:create`, `spec:sync` (publishes to Plane + Wiki.js), `spec:status`, `spec:init`.
- [ ] T104 [P] Author `manifests/cicd/*.yaml` for `cicd:init`, `cicd:check`, `cicd:health`, `cicd:smoke`, `cicd:pipeline`, `cicd:container`, `cicd:infra-init`, `cicd:infra-discover`, `cicd:infra-pipeline` (carry-over from source power-packs).
- [ ] T105 [P] Author `manifests/security/*.yaml` for `security:scan`, `security:quick`, `security:deep`, `security:explain`.
- [ ] T106 [P] Author `manifests/secrets/*.yaml` for `secrets:get`, `secrets:set`, `secrets:delete`, `secrets:list`, `secrets:run`, `secrets:validate`, `secrets:rotate`, `secrets:ui`.
- [ ] T107 [P] Author `manifests/qa/*.yaml` for `qa:test`, `qa:help`.
- [ ] T108 [P] Author `manifests/agents-md/*.yaml` for `agents-md:lint`, `agents-md:help`.
- [ ] T109 [P] Author `manifests/second-opinion/*.yaml` for `second-opinion:start`, `second-opinion:models`, `second-opinion:help`, and a new `second-opinion:grill-plan` wrapping the `grill_plan` MCP tool.
- [ ] T110 [P] Author `manifests/project/*.yaml` for `project:init` , `project:lite`, `project:next`.

---

## Phase 11: Polish & Cross-Cutting

**Purpose**: Finalize docs, CI, performance verification, and release tagging.

- [ ] T111 Populate `README.md` at repo root with project purpose, quickstart link, badge row, and the four first-class runtimes.
- [ ] T112 [P] Populate `CONTRIBUTING.md` explaining the spec-kit workflow, the constitution, the grill gate, and the manifest-first rule.
- [ ] T113 [P] Populate `SECURITY.md` with responsible-disclosure contact and a pointer to the tiered secrets layer.
- [ ] T114 [P] Populate `CODE_OF_CONDUCT.md` using the Contributor Covenant template.
- [ ] T115 Author `.woodpecker.yml` at repo root implementing lint / test / verify + deploy stages, and confirm it passes `cicd:woodpecker-checklist` in validator mode.
- [ ] T116 [P] Implement `make verify` to run `ruff check`, `mypy src/`, `pytest -m "unit or integration"`, and the perf suite.
- [ ] T117 [P] Implement `make lint` to run only `ruff check` + `mypy src/` + `agent-power-pack lint agents-md --json`.
- [ ] T118 Run `agent-power-pack grill yourself` manually against the whole foundation feature and attach the transcript to the PR (validates spec User Story 4 end-to-end).
- [ ] T119 Bump `pyproject.toml` version to `0.1.0` and tag `v0.1.0` on the merge commit.
- [ ] T120 Update `MEMORY.md` and `CHANGELOG.md` with the v0.1.0 release notes.

---

## Dependencies

- **Phase 1 (Setup)** blocks **Phase 2 (Foundational)**.
- **Phase 2 (Foundational)** blocks ALL user story phases.
- **US1 (Phase 3)**, **US2 (Phase 4)**, and **US3 (Phase 5)** are P1 and MUST all complete for a minimal useful release, but within each phase tasks marked [P] can run in parallel.
- **US4 (Phase 6)** depends on Phase 2 only (independent of US1–US3 for core logic), but wiring into `flow:finish` depends on US1 (CLI) being present.
- **US5 (Phase 7)** depends on Phase 2 only.
- **US6 (Phase 8)** depends on Phase 2 and US3 (MCP container + Plane/Wiki.js servers must exist for connectivity probes to succeed).
- **Phase 9 (Woodpecker checklist)** depends on Phase 2 only; can run in parallel with user stories.
- **Phase 10 (skill catalog port)** depends on Phase 2 (manifest schema) and US1 (adapters must exist to install the manifests).
- **Phase 11 (Polish)** depends on every preceding phase.

## Parallel Execution Examples

**After Phase 2 completes**, three P1 phases can be staffed concurrently:

- Developer A drives Phase 3 (US1): tasks T021–T032
- Developer B drives Phase 4 (US2): tasks T033–T045
- Developer C drives Phase 5 (US3): tasks T046–T062

**Within Phase 5**, the six server ports (T050–T055) are independent and parallel.

**Within Phase 10**, all nine manifest-family tasks (T102–T110) are file-disjoint and parallel.

## Implementation Strategy

**MVP scope**: Phases 1 + 2 + 3 (US1). This alone delivers "install agent-power-pack on Claude Code and Codex CLI from one repo with no hand-editing" — spec SC-001. Everything else (linter, MCP container, grills, Plane/Wiki.js, woodpecker checklist) is layered on in subsequent increments.

**Recommended delivery order**:

1. **MVP release**: Phases 1 → 2 → 3 (US1).
2. **Gate release**: add Phase 4 (US2) — AGENTS.md lint as a real gate.
3. **Container release**: add Phase 5 (US3) — single-container MCP.
4. **Grill release**: add Phases 6 + 7 (US4 + US5) — grill skills.
5. **Defaults release**: add Phase 8 (US6) — Plane/Wiki.js defaults + project:init wizard.
6. **Checklist release**: add Phase 9 — Woodpecker checklist.
7. **Catalog release**: add Phase 10 — full skill catalog port.
8. **v0.1.0 tag**: Phase 11 polish.

Total tasks: **120**. Tasks per story: US1=12, US2=13, US3=17, US4=9, US5=7, US6=16. Setup=10, Foundational=10, Woodpecker=7, Catalog=9, Polish=10.
