# Feature Specification: Agent Power Pack Foundation

**Feature Branch**: `001-foundation`
**Created**: 2026-04-11
**Status**: Draft
**Input**: User description: "Initialize agent-power-pack — a universal agentic
power pack that unifies claude-power-pack and codex-power-pack, runs on Claude
Code / Codex CLI / Gemini CLI / Cursor, lints AGENTS.md, ships a single
multi-protocol MCP container including second-opinion, plane and wikijs, and
includes both grill-me (vendored from mattpocock/skills) and grill-yourself."

## Clarifications

### Session 2026-04-11

- Q: Skill manifest format? → A: YAML (`manifests/<family>/<skill>.yaml`)
- Q: Default secrets layer? → A: Tiered dotenv → env-file → AWS Secrets Manager, with the Rust-based aws-secretsmanager-agent sidecar (Docker-first) as the default production tier
- Q: Primary implementation language? → A: Python 3.11+ with uv (Rust sidecar only for aws-secretsmanager-agent)
- Q: grill-yourself trigger heuristic? → A: Diff-size threshold (defaults: >200 changed lines OR >5 files; thresholds configurable in `.specify/grill-triggers.yaml`)
- Q: MCP container base image? → A: `mcr.microsoft.com/playwright/python:v1.x-jammy` (pre-baked browsers, single-container-friendly)

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Bootstrap a project on any supported runtime (Priority: P1)

A developer initializes agent-power-pack in a fresh repo and expects the
toolchain to work identically whether they open it in Claude Code, Codex CLI,
Gemini CLI, or Cursor. The neutral skill manifests are transpiled into the
right per-runtime layout, the canonical `AGENTS.md` is generated alongside
`CLAUDE.md` / `GEMINI.md` / `.cursorrules`, and the `agents-md:lint` skill is
wired into the flow gates.

**Why this priority**: Multi-runtime support is the core differentiator
versus the existing power-packs. Without it, agent-power-pack is just a
rename. Everything else (MCP container, grill skills, Plane/Wiki.js) is
useless if a developer can't install on their preferred runtime.

**Independent Test**: From a clean directory, run `make install RUNTIME=claude`,
then again with `RUNTIME=codex`, then `RUNTIME=gemini`, then `RUNTIME=cursor`.
Each install MUST produce a working skill catalog visible to that runtime,
with no manual editing. Smoke test: invoke `/agents-md:lint` (or equivalent
runtime trigger) on each and confirm identical output.

**Acceptance Scenarios**:

1. **Given** an empty repo, **When** `make install RUNTIME=claude` runs,
   **Then** `.claude/skills/` is populated, `CLAUDE.md` is generated from
   `AGENTS.md`, and `claude --print "/agents-md:lint"` returns a clean lint.
2. **Given** the same repo, **When** `make install RUNTIME=codex` runs after,
   **Then** `.codex/skills/` and `~/.codex/config.toml` are populated and
   the codex skill catalog matches the claude one.
3. **Given** any supported runtime, **When** the user invokes a skill present
   in the neutral manifest, **Then** the runtime executes it without errors.

---

### User Story 2 — AGENTS.md is canonical, all other instruction files are generated (Priority: P1)

A developer edits `AGENTS.md` to add a new Make target reference. On the next
`/flow:check`, `agents-md:lint` verifies the target exists in the Makefile,
regenerates `CLAUDE.md` / `GEMINI.md` / `.cursorrules` from `AGENTS.md`, and
fails the check if any generated file is stale or any referenced target,
command, Docker service, or CI file is missing.

**Why this priority**: The whole point of "linting to define critical project
infrastructure" is enforcement. Without P1 status, drift returns and the
linter becomes advice nobody reads.

**Independent Test**: Edit `AGENTS.md` to reference a Make target that does
not exist; run `/agents-md:lint`; confirm exit code is non-zero and the
message names the missing target. Add the target; rerun; confirm clean.

**Acceptance Scenarios**:

1. **Given** `AGENTS.md` references `make verify`, **When** `make verify`
   exists in the Makefile, **Then** `agents-md:lint` passes that check.
2. **Given** `AGENTS.md` was edited but `CLAUDE.md` was not regenerated,
   **When** `agents-md:lint` runs, **Then** it reports "stale generated
   file: CLAUDE.md" and exits non-zero.
3. **Given** a hand-edit to `CLAUDE.md`, **When** the linter runs, **Then**
   the hand-edit is reverted and the user is told to edit `AGENTS.md`.
4. **Given** a missing required section ("CI/CD Protocol"), **When** the
   linter runs, **Then** it fails with a schema error naming the section.

---

### User Story 3 — Single MCP container with multi-transport for all servers (Priority: P1)

The MCP servers (`second-opinion`, `plane`, `wikijs`, `nano-banana`,
`playwright`, `woodpecker`) ship in ONE container image. The container exposes
each server on TWO ports simultaneously: a stdio/HTTP non-streaming port for
Claude Code, and an SSE/streamable port for Codex CLI. A developer runs
`make mcp-up` once and both runtimes can attach.

**Why this priority**: Two separate container fleets (one per runtime) is the
status quo of the existing power-packs and the main pain point this project
addresses. Unifying this is the second-largest differentiator after
multi-runtime skill support.

**Independent Test**: `make mcp-up` then point a Claude Code session and a
Codex CLI session at the same container concurrently; both invoke a
`second-opinion` tool and both succeed.

**Acceptance Scenarios**:

1. **Given** `make mcp-up`, **When** Claude Code calls `second-opinion.review`
   over stdio/HTTP, **Then** the tool returns a result.
2. **Given** the same container, **When** Codex CLI calls
   `second-opinion.review` over SSE, **Then** the tool returns a result.
3. **Given** the container is running, **When** `curl /healthz` is called
   on each server's port, **Then** all six servers report healthy.

---

### User Story 4 — Grill-yourself runs before risky changes (Priority: P2)

Before any `/flow:finish` that touches the MCP container, the skill manifest
format, or `AGENTS.md` itself, `grill-yourself` automatically generates a list
of pre-flight questions, answers them, and attaches the transcript to the PR.
The user can also invoke `grill-yourself` manually on any plan.

**Why this priority**: Catches assumptions before risky changes, but the
project ships without it if needed — the gate is enforcement of an
already-valuable practice.

**Independent Test**: Open a PR that edits `AGENTS.md`; `/flow:finish`;
confirm the grill-yourself transcript is in the PR description.

**Acceptance Scenarios**:

1. **Given** a PR touching `mcp-container/`, **When** `/flow:finish` runs,
   **Then** a `grill-yourself` transcript is generated and attached.
2. **Given** a PR touching only README typos, **When** `/flow:finish` runs,
   **Then** `grill-yourself` is skipped.
3. **Given** a user invokes `grill-yourself` manually with a plan,
   **Then** the agent produces and answers ≥5 grill questions.

---

### User Story 5 — Grill-me available for interactive user interrogation (Priority: P2)

A user types `grill me on this plan` (or `/grill:me`) and the agent invokes
the vendored `grill-me` skill from mattpocock/skills, walking the decision
tree one question at a time until shared understanding is reached.
Attribution is preserved in `ATTRIBUTION.md` and the skill manifest header.

**Why this priority**: High user value but parallel to grill-yourself; either
can ship first.

**Independent Test**: Trigger `/grill:me` with a plan; confirm the agent asks
sequential single-question rounds and produces a final summary.

**Acceptance Scenarios**:

1. **Given** the user invokes `/grill:me`, **When** they describe a plan,
   **Then** the agent asks one question at a time with a recommended answer.
2. **Given** the skill is installed, **When** `cat skills/grill-me/SKILL.md`
   is shown, **Then** the file header credits
   `https://github.com/mattpocock/skills/tree/main/grill-me`.
3. **Given** the project README, **When** loaded, **Then** `ATTRIBUTION.md`
   is linked and lists mattpocock/skills with its license.

---

### User Story 6 — Plane is the default issue tracker, Wiki.js the default knowledge base (Priority: P2)

`/spec:sync` mirrors specs to a configured Plane workspace as issues/cycles
and to a configured Wiki.js space as pages. `/issue:*` (renamed from
`/github:issue-*`) operates on Plane via `plane-mcp`. `/docs:c4` publishes
C4 architecture diagrams directly to Wiki.js pages. The PowerPoint exporter
(`/docs:pptx`) is removed.

**Why this priority**: The substitutions are the user's stated direction but
not blocking — `gh` issue access remains as an opt-in fallback adapter.

**Independent Test**: Configure Plane and Wiki.js URLs/tokens via secrets;
run `/spec:sync` on a sample spec; confirm an issue lands in Plane and a
page lands in Wiki.js.

**Acceptance Scenarios**:

1. **Given** valid Plane credentials, **When** `/issue:create` runs,
   **Then** an issue is created in the configured Plane workspace.
2. **Given** valid Wiki.js credentials, **When** `/docs:c4 publish` runs
   on a diagram source, **Then** a wiki page is created or updated.
3. **Given** `/docs:pptx` is invoked, **When** any runtime runs it,
   **Then** the skill is reported missing (removed from the catalog).

---

### User Story 7 — `project:lite` and `project:next` for fast bootstrapping and issue triage (Priority: P1)

A developer working solo across many small repos needs (a) a lightweight
scaffold that gives them the AGENTS.md lint discipline without the full MCP
container, Plane, Wiki.js, and spec-kit ceremony, and (b) a one-command
answer to "what should I work on next?" from the issue backlog.

**Why this priority**: `project:next` is the entry point to the dogfood loop
— without it, every iteration starts with a manual issue tracker scan.
`project:lite` enables fast adoption across personal/POC projects, expanding
the user base beyond teams that can run the full stack. Both are critical
for velocity.

**Independent Test**: (a) `app:lite my-script` in a temp dir produces a
valid `AGENTS.md`, generated runtime files, and a stub `Makefile` that
passes `agents-md:lint`, with no Plane/Wiki.js prompts. (b) `app:next`
in a repo with 10 open issues (5 `p1`, 5 `p2`, 2 blocked) returns a `p1`
unblocked issue with a ready-to-paste `/flow:start <N>` invocation.

**Acceptance Scenarios**:

1. **Given** a fresh empty directory, **When** `app:lite my-script` runs,
   **Then** `AGENTS.md` exists with six required sections, `CLAUDE.md` is
   generated, `Makefile` has `lint`, `test`, `verify` targets, and no
   `.specify/` directory is created.
2. **Given** an `app:lite`-scaffolded project, **When**
   `agent-power-pack lint agents-md` runs, **Then** the lint passes.
3. **Given** a repo with 10 open GitHub issues labeled `p1`/`p2`, some
   with `blockedBy` dependencies resolved and some not, **When**
   `app:next` runs, **Then** the recommended issue is a `p1` issue
   whose dependencies are all closed, and the output ends with
   `/flow:start <N>`.
4. **Given** `app:next --top 3` runs, **Then** the output shows three
   candidates ranked by priority × unblocked × phase.
5. **Given** the Plane backend is configured, **When** `app:next` runs,
   **Then** it queries Plane (not GitHub) and returns a Plane issue ID.

---

### Edge Cases

- A user installs on a runtime not yet supported by a transpiler adapter →
  `make install` fails fast with a clear "no adapter for RUNTIME=foo" error.
- `AGENTS.md` is deleted → `agents-md:lint` fails with "missing canonical
  source" before checking sections.
- The MCP container starts but Plane is unreachable → `/issue:*` skills
  return a structured error referencing the configured Plane URL; the
  container itself stays healthy.
- A skill is added that targets only one runtime → the manifest validator
  rejects it at PR time, citing Principle I.
- `grill-me` skill license changes upstream → vendor copy is pinned by SHA
  and `make update-vendored-skills` is the only way to refresh.
- Two runtimes attach to the MCP container simultaneously and call the same
  long-running tool → both calls succeed independently; no shared mutable
  state across sessions.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001** The repo MUST host a `manifests/` directory containing one
  neutral skill manifest per skill in the catalog.
- **FR-002** The repo MUST provide transpiler adapters for at least Claude
  Code and Codex CLI at v0.1.0; Gemini CLI and Cursor adapters MAY ship later
  but are required by v1.0.0.
- **FR-003** `AGENTS.md` MUST be the only hand-edited instruction file. The
  install pipeline MUST regenerate `CLAUDE.md`, `GEMINI.md`, and `.cursorrules`
  from `AGENTS.md` content sections.
- **FR-004** `agents-md:lint` MUST verify (a) required sections present, (b)
  every referenced Make target / command / Docker service / CI file exists,
  (c) generated instruction files are in sync.
- **FR-005** The MCP container MUST package `second-opinion`, `plane`,
  `wikijs`, `nano-banana`, `playwright`, and `woodpecker` servers in a single
  image and expose each on both a stdio/non-streaming port and an SSE/
  streamable port.
- **FR-006** `second-opinion-mcp` MUST expose a `grill_plan` tool used by
  `grill-yourself` for external-LLM grilling mode.
- **FR-007** The `grill-me` skill MUST be vendored from
  `https://github.com/mattpocock/skills/tree/main/grill-me`, pinned by commit
  SHA, with attribution preserved in the skill manifest header and a top-level
  `ATTRIBUTION.md` file linking back to the upstream repo and license.
- **FR-008** The `grill-yourself` skill MUST run automatically as a gate
  before `/flow:finish` when the pending change exceeds EITHER of two
  diff-size thresholds: **>200 changed lines** OR **>5 changed files**
  (measured against the merge base). Both thresholds MUST be configurable
  in `.specify/grill-triggers.yaml` (keys: `max_lines`, `max_files`) and
  MUST be overridable per-PR via a `grill-yourself: force|skip` trailer in
  the commit message. When triggered, `grill-yourself` MUST attach its
  transcript to the PR description. Path-based triggers are explicitly out
  of scope to keep the heuristic uniform across all areas of the repo.
- **FR-009** `/spec:sync` MUST publish spec artifacts to both Plane (as
  issues/cycles) and Wiki.js (as pages) when those integrations are configured.
- **FR-010** `/issue:*` skills MUST default to `plane-mcp`. A `gh`-backed
  adapter MAY be enabled via opt-in flag.
- **FR-011** `/docs:c4` MUST publish to Wiki.js pages. `/docs:pptx` MUST NOT
  exist in the v0.1.0 catalog.
- **FR-012** The `sequential-thinking` skill MUST NOT exist in the catalog;
  any existing reference to it in ported code MUST be removed.
- **FR-013** Every skill MUST declare in its manifest the runtimes it supports;
  the manifest validator MUST reject any skill that lists fewer than ALL
  first-class runtimes (per Principle I).
- **FR-014** The repo MUST ship a `Makefile` with at minimum: `install`,
  `mcp-up`, `mcp-down`, `verify`, `lint`, `test`, `update-vendored-skills`.
- **FR-015** A `app:init` skill MUST bootstrap a NEW project that uses
  agent-power-pack: scaffold `AGENTS.md`, generate per-runtime instruction
  files, write a starter `Makefile`, install the MCP container compose file,
  and run a guided configuration step for Plane and Wiki.js (see FR-016).
- **FR-016** `app:init` MUST offer a guided configuration step for the
  preferred external tools. For each of Plane and Wiki.js it MUST: (a) detect
  any existing credentials/URLs in the secrets layer; (b) if absent, prompt
  the user for base URL, workspace/space slug, and API token, with `--skip`
  to defer; (c) write captured values into the secrets layer (never plain
  files); (d) run a one-shot connectivity check against the configured
  endpoint and report pass/fail; (e) record the chosen workspace/space in
  `AGENTS.md` under a generated "External Systems" section. Skipped tools
  MUST be re-promptable via `app:init --reconfigure plane|wikijs`.
- **FR-016a** The secrets layer MUST be tiered: `dotenv` (dev default) →
  `env-file` → `aws-secretsmanager` (production default). The AWS tier MUST
  read secrets through the official Rust-based
  [`aws-secretsmanager-agent`](https://github.com/awslabs/aws-secretsmanager-agent)
  sidecar, packaged as a Docker container, started alongside the MCP container
  by `make mcp-up`. No skill, MCP server, or init script may read AWS Secrets
  Manager directly — every production read MUST traverse the sidecar's local
  HTTP endpoint. Dotenv and env-file tiers remain available as fallbacks and
  are selected automatically when the sidecar is not running.
- **FR-017** A `cicd:woodpecker-checklist` skill MUST ship a checklist
  template derived from learned findings in
  [`cooneycw/woodpecker-baseline`](https://github.com/cooneycw/woodpecker-baseline).
  The checklist MUST cover at minimum: pinned image tags (no `:latest`);
  `git config --global safe.directory "*"` for root-in-container git ops;
  no unjustified `failure: ignore`; stale-commit guard in deploy scripts;
  concurrent-deploy lock with documented protected resource; two-phase
  readiness (liveness + capability) with reverse-proxy wait buffers;
  secrets-readable-in-first-step check; explicit `when` filters and
  `depends_on` (not sequential naming); required agent labels for
  privileged deploys; pre-merge non-prod test deploy. The checklist MUST be
  runnable both as an interactive walkthrough and as a non-interactive
  validator over a Woodpecker `.woodpecker.yml` file.
- **FR-018** `cicd:init` MUST invoke `cicd:woodpecker-checklist` in
  validator mode against any generated `.woodpecker.yml`, and MUST refuse to
  finalize a CI/CD setup that fails any non-waivable checklist item.
- **FR-019** A `project:lite` skill MUST bootstrap a minimal project that
  uses agent-power-pack without the full MCP container, Plane, Wiki.js,
  or spec-kit ceremony. It MUST: (a) create `AGENTS.md` from a reduced
  template containing only the six required sections; (b) generate the
  per-runtime instruction files (`CLAUDE.md`, `GEMINI.md`, `.cursorrules`);
  (c) create a stub `Makefile` with `lint`, `test`, and `verify` targets;
  (d) run `agents-md:lint` to confirm the scaffold is clean. It MUST NOT
  prompt for Plane, Wiki.js, or secrets configuration, bring up the MCP
  container, or create a spec-kit `.specify/` directory. Use case: small
  scripts, POCs, and personal utilities that benefit from the AGENTS.md
  lint discipline but not the full infrastructure. `project:lite` MUST be
  invocable as `app:lite` (alias).
- **FR-020** A `project:next` skill MUST query the active issue backend
  (Plane via `plane-mcp` when configured, otherwise GitHub Issues via
  `gh`) and recommend the single best issue to work on next. The ranking
  algorithm MUST factor in: (a) priority labels (`p1` before `p2`);
  (b) unblocked status — issues whose `blockedBy` dependencies (if any)
  are all closed; (c) parallel safety — issues labeled `parallel` are
  preferred when the user already has an active worktree on another issue;
  (d) phase ordering — lower phase numbers before higher. The skill MUST
  output the issue number, title, priority, phase, and a one-line
  rationale for the recommendation, followed by a ready-to-paste
  `/flow:start <N>` invocation. If no open issues match, report "No
  actionable issues found." `project:next` MUST be invocable as
  `app:next` (alias). The skill MUST also support a `--top N` flag to
  show the top N candidates instead of just the single best.
- **FR-015a** `project:init` (canonical name) and `app:init` (alias)
  refer to the same skill defined in FR-015 / FR-016 / FR-016a. The
  `project:` family namespace is the user-facing prefix; `app:` is the
  shorthand. Both MUST resolve to the same manifest and the same
  implementation. `project:lite` = `app:lite` and `project:next` =
  `app:next` follow the same aliasing convention.

### Key Entities *(include if feature involves data)*

- **Skill Manifest**: A neutral **YAML** description of a skill, stored at
  `manifests/<family>/<skill>.yaml`. Required top-level keys: `name`,
  `family`, `description`, `triggers` (list), `runtimes` (list — must cover
  every first-class runtime per Principle I), `prompt` (multi-line body),
  `mcp_tools` (list, may be empty), `attribution` (object with `source`,
  `commit_sha`, `license` — required for vendored skills, optional for
  native). Manifests are hand-authored; adapters read them at install time
  and emit per-runtime layouts.
- **Runtime Adapter**: Code that takes a set of skill manifests and emits
  the runtime-specific layout (`.claude/skills/`, `.codex/skills/`,
  `.gemini/`, `.cursor/`). Lives in `adapters/<runtime>/`.
- **MCP Container**: The single Docker image hosting all six MCP servers
  with multi-port exposure. Defined in `mcp-container/Dockerfile`,
  `compose.yaml`, and `mcp-container/servers/<name>/`.
- **AGENTS.md**: Canonical project-instructions file; the only hand-edited
  instruction document in the repo.
- **Generated Instruction Files**: `CLAUDE.md`, `GEMINI.md`, `.cursorrules` —
  derived from `AGENTS.md`; any hand-edits are reverted by the linter.
- **Vendored Skill**: A third-party skill (currently only `grill-me` from
  mattpocock/skills) imported under `vendor/skills/<name>/`, pinned by SHA,
  with attribution preserved.
- **Grill Transcript**: Output of `grill-yourself`; markdown artifact stored
  under `.specify/grills/<spec-id>.md` and attached to PRs by `/flow:finish`.

## Success Criteria *(mandatory)*

- **SC-001** A developer can install agent-power-pack on Claude Code AND
  Codex CLI from the same repo with no per-runtime hand-editing.
- **SC-002** A spec mirrored via `/spec:sync` appears in both the configured
  Plane workspace and Wiki.js space within one command invocation.
- **SC-003** `agents-md:lint` catches every staleness scenario in the
  test suite (missing section, missing make target, stale generated file,
  hand-edit to generated file).
- **SC-004** A single `make mcp-up` brings up one container that serves
  both Claude Code (stdio) and Codex CLI (SSE) clients concurrently.
- **SC-005** Every PR touching `mcp-container/`, `manifests/`, or `AGENTS.md`
  has a `grill-yourself` transcript attached automatically.
- **SC-006** The `grill-me` skill in the installed catalog credits
  mattpocock/skills in its header and the repo `ATTRIBUTION.md` lists the
  upstream commit SHA and license.
- **SC-007** Adding a new runtime requires writing one adapter under
  `adapters/<runtime>/` and zero changes to `manifests/`.
- **SC-008** `app:init` on a fresh project produces a working agent-power-pack
  installation with Plane and Wiki.js connectivity verified (or explicitly
  deferred) in a single guided run.
- **SC-009** `cicd:woodpecker-checklist` rejects every known-bad pattern
  from the woodpecker-baseline findings (test fixture per finding) and
  passes a clean `.woodpecker.yml`.
- **SC-010** `app:lite` in an empty directory produces a valid
  `AGENTS.md` + generated instruction files + stub `Makefile` that
  passes `agents-md:lint`, with no Plane/Wiki.js prompts fired and no
  `.specify/` directory created.
- **SC-011** `app:next` against a repo with a mixed backlog (varying
  priorities, some blocked, some parallel-safe) returns the correct
  top-ranked unblocked issue and a ready-to-paste `/flow:start <N>`
  invocation. `--top 3` returns 3 ranked candidates.

## Technical Constraints

- **Implementation language**: Python 3.11+ managed by [`uv`](https://docs.astral.sh/uv/)
  for every component EXCEPT the AWS Secrets Manager sidecar, which is the
  official Rust-based `aws-secretsmanager-agent`. No other language may be
  introduced without a constitutional amendment.
- **Package management**: `uv` workspaces; pinned Python versions in
  `pyproject.toml`. No `pip`, `poetry`, or `conda` in the primary toolchain.
- **Containerization**: Docker-first. `make mcp-up` brings up the MCP
  container AND the aws-secretsmanager-agent sidecar via a single compose
  file.
- **MCP container base image**: `mcr.microsoft.com/playwright/python:v1.x-jammy`
  (Ubuntu Jammy, pre-baked Chromium / Firefox / WebKit). Chosen so the
  `playwright-persistent` MCP server can coexist with the other five servers
  in a single container without a multi-hundred-MB browser install at build
  time. The exact Playwright patch version is pinned in `mcp-container/Dockerfile`
  and bumped via PR.

## Out of Scope (v0.1.0)

- Authoring NEW skills beyond porting the existing claude/codex-power-pack
  catalog (minus removed items).
- Migrating existing claude-power-pack or codex-power-pack USERS automatically;
  agent-power-pack is greenfield and the source repos remain on their own
  release lines.
- Authentication flows for Plane or Wiki.js beyond reading tokens from the
  existing secrets layer.
- A web UI. CLI + agent slash commands are the only surface.
- Replacing Woodpecker with another CI platform.
