<!--
SYNC IMPACT REPORT
==================
Version change: (none) → 0.1.0   [INITIAL RATIFICATION]
Bump rationale:  First ratified version. No prior constitution existed; the
                 file was scaffolded from .specify/templates/constitution-template.md
                 by `specify init` and is now filled with concrete principles.

Modified principles:
  - (n/a — initial ratification)

Added sections:
  - Core Principles
      I.   Multi-Runtime First (NON-NEGOTIABLE)
      II.  AGENTS.md is Canonical
      III. Single MCP Container, Multi-Transport
      IV.  Lint or Lose
      V.   Grill Before You Build
  - Preferred External Tools (Plane, Wiki.js, Woodpecker CI)
  - Skill Catalog Scope
  - Development Workflow & Quality Gates
  - Governance

Removed sections:
  - All [PLACEHOLDER] stubs from the original template

Templates requiring updates:
  - .specify/templates/plan-template.md          ✅ no edit needed
      (Constitution Check section is generic; gates will be derived at
       /speckit.plan time from Principles I–V.)
  - .specify/templates/spec-template.md          ✅ no edit needed
      (Generic — already used for specs/001-foundation/spec.md.)
  - .specify/templates/tasks-template.md         ✅ no edit needed
      (No new task TYPE introduced beyond standard categories.)
  - .specify/templates/checklist-template.md     ✅ no edit needed
  - .specify/templates/agent-file-template.md    ✅ no edit needed
  - .claude/skills/speckit-*/SKILL.md            ✅ no edit needed
      (Generic spec-kit skills installed by `specify init`.)

Follow-up TODOs:
  - (none) — all placeholders resolved.
-->

# Agent Power Pack Constitution

A universal agentic power pack for coding environments. Successor to and unification
of [`cooneycw/claude-power-pack`](https://github.com/cooneycw/claude-power-pack)
and [`cooneycw/codex-power-pack`](https://github.com/cooneycw/codex-power-pack),
extended to support additional agent runtimes through a neutral skill manifest layer.

## Core Principles

### I. Multi-Runtime First (NON-NEGOTIABLE)
Every skill, command, and MCP integration MUST work across all first-class agent
runtimes: Claude Code, Codex CLI, Gemini CLI, and Cursor. Skills are authored ONCE
in a neutral manifest format and transpiled per runtime at install time. A skill
that only runs on one runtime is rejected. New runtimes are added by writing a new
transpiler adapter, never by forking the skill catalog.

### II. AGENTS.md is Canonical
`AGENTS.md` at the repo root is the single source of truth for project instructions.
`CLAUDE.md`, `GEMINI.md`, `.cursorrules`, and any other per-runtime instruction files
are GENERATED from `AGENTS.md` during install and refreshed on every edit. Hand-edits
to generated files are reverted by the linter. Rationale: AGENTS.md is the emerging
cross-agent standard; one canonical file eliminates drift.

### III. Single MCP Container, Multi-Transport
All MCP servers (`second-opinion`, `plane`, `wikijs`, `nano-banana`, `playwright`,
`woodpecker`) ship in a SINGLE container image with multiple ports and protocols
exposed simultaneously. Codex clients consume the streaming/SSE transport; Claude
Code clients consume the stdio (or non-streaming HTTP) transport. One image, one
deploy unit, per-runtime config picks the right port. The legacy `sequential-thinking`
skill is removed — `grill-yourself` supersedes it.

### IV. Lint or Lose
The `agents-md:lint` skill is a quality gate, not advisory. It MUST verify:
(a) required sections are present in `AGENTS.md` (CI/CD Protocol, Quality Gates,
Troubleshooting, Available Commands, Docker Conventions, Deployment);
(b) every Make target, command, Docker service, and CI file referenced in `AGENTS.md`
actually exists in the repo;
(c) generated instruction files (`CLAUDE.md`, `GEMINI.md`, `.cursorrules`) are in
sync with the current `AGENTS.md`.
Lint failures block `flow:finish`, `flow:auto`, and CI merge gates. External-system
liveness checks (Plane, Wiki.js, Woodpecker URLs) are explicitly out of scope to keep
the linter deterministic and offline-safe.

### V. Grill Before You Build
Two grill skills are first-class members of the catalog:
- **`grill-me`** — interactive user interrogation skill from
  [mattpocock/skills](https://github.com/mattpocock/skills/tree/main/grill-me).
  Vendored with full attribution preserved in the skill manifest and a top-level
  `ATTRIBUTION.md`. Used when the user wants to be interviewed about a plan.
- **`grill-yourself`** — pre-flight self-interrogation. Before executing any
  non-trivial plan, the agent generates and answers grill-style questions itself,
  surfacing assumptions, edge cases, and unknowns. The transcript is logged for
  user review. Replaces the deprecated `sequential-thinking` skill.

## Preferred External Tools

Agent Power Pack standardizes on a self-hostable, open-source toolchain.
These are the PREFERRED — and default — integrations. Alternatives are
permitted only via additional adapters; the core skill catalog targets these:

- **[Plane](https://plane.so/)** is the preferred issue tracker and replaces
  GitHub Issues. `spec:sync`, `flow:start`, and the `issue:*` family
  (renamed from the former `github:issue-*`) target a Plane workspace via
  `plane-mcp`. Issues, cycles, and modules map onto flow gates.
- **[Wiki.js](https://js.wiki/)** is the preferred knowledge base and replaces
  Confluence-style docs. Spec artifacts, C4 architecture diagrams, and grill
  transcripts are published as wiki pages via `wikijs-mcp`.
- **[Woodpecker CI](https://woodpecker-ci.org/)** is the preferred CI/CD
  platform for the `/cicd:*` family, carried over from both source power-packs.

## Skill Catalog Scope

The skill catalog from both source power-packs ports forward, trimmed and
retargeted at the preferred tools above:

- **Documentation (`docs:*`) is trimmed.** PowerPoint export (`docs:pptx`)
  is REMOVED — the deliverable surface is Wiki.js, not slide decks. C4
  architecture diagrams (`docs:c4`) are KEPT and publish directly to Wiki.js
  pages.
- **Issue commands target Plane.** `issue:*` (formerly `github:issue-*`)
  uses `plane-mcp`. Plain `gh` issue access remains available as an opt-in
  adapter but is not the default.

The `second-opinion-mcp` server retains its multi-backend code review surface
(Gemini, GPT, Claude, o4-mini, screenshot analysis, interactive sessions) and
gains a `grill_plan` tool used by `grill-yourself` when the user opts for
external (vs self) interrogation.

In-scope skill families (conceptual names — see
[Runtime Invocation Matrix](../../specs/001-foundation/contracts/runtime-invocation-matrix.md)
for per-runtime invocation syntax): `flow:*`, `spec:*`, `cicd:*`,
`docs:c4` (only), `security:*`, `secrets:*`, `qa:*`, `agents-md:*`,
`second-opinion:*`, `issue:*` (Plane), `wiki:*` (Wiki.js), `project:*`,
`grill:*`.
Out of scope: `sequential-thinking`, `docs:pptx`.

## Development Workflow & Quality Gates

- **Spec-driven.** All non-trivial features begin with a spec-kit specify
  pass and move through plan and tasks phases before implementation.
  Specs are mirrored to Plane (as issues/cycles) and Wiki.js (as pages) by
  `spec:sync`.
- **Flow lifecycle.** Work flows through `flow:start` → `flow:check` →
  `flow:finish`, with worktree isolation and quality gates enforced at each
  step. `flow:finish` runs `agents-md:lint`, `make verify`, and the
  generated-files freshness check; failure blocks the merge. Each runtime
  invokes these skills through its native interaction model (see
  [Runtime Invocation Matrix](../../specs/001-foundation/contracts/runtime-invocation-matrix.md)).
- **Grill gates.** `grill-yourself` runs automatically before any
  `flow:finish` on changes touching the MCP container, the skill manifest
  format, or `AGENTS.md` itself. Transcripts are attached to the PR.
- **Single source of truth.** `AGENTS.md` governs runtime behavior; this
  Constitution governs design intent. When they conflict, the Constitution
  wins and `AGENTS.md` is updated to match.

## Governance

This Constitution supersedes ad-hoc practices in `AGENTS.md` and any per-runtime
instruction file. Amendments require:
1. A spec-kit spec describing the change and its rationale.
2. A `grill-yourself` transcript covering its second-order effects on existing
   skills, MCP transports, and runtime adapters.
3. A migration note in `CHANGELOG.md` if any skill, MCP tool, or generated file
   changes shape.

PRs that modify the skill manifest format, the MCP container image, or
`AGENTS.md` linter rules MUST cite the constitutional principle they uphold or
amend. Complexity that does not trace to a principle is rejected.

**Version**: 0.1.0 | **Ratified**: 2026-04-11 | **Last Amended**: 2026-04-11
