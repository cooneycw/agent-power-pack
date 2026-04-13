# agent-power-pack

> A universal agentic power pack for coding environments. Works across
> Claude Code, Codex CLI, Gemini CLI, and Cursor from a single source of
> truth.

**Status**: foundation (v0.1.0). Successor to and unification
of [`cooneycw/claude-power-pack`](https://github.com/cooneycw/claude-power-pack)
and [`cooneycw/codex-power-pack`](https://github.com/cooneycw/codex-power-pack).

## What's in the box

Short version, per the [Constitution](./.specify/memory/constitution.md):

- **Multi-runtime first.** Skills are authored ONCE as neutral YAML
  manifests under `manifests/` and transpiled to each runtime's native
  layout by per-runtime adapters under `adapters/`.
- **`AGENTS.md` is canonical.** `CLAUDE.md`, `GEMINI.md`, and
  `.cursorrules` are generated from it; the `agents-md:lint` skill
  reverts hand-edits to the generated files.
- **Single MCP container.** One Docker image hosts `second-opinion`,
  `plane`, `wikijs`, `nano-banana`, `playwright`, and `woodpecker`,
  each exposed on both a stdio/non-streaming HTTP port (Claude Code)
  and a streamable HTTP port (Codex CLI; SSE may remain available for
  compatibility on the high-port listener).
- **Plane replaces GitHub Issues** and **Wiki.js replaces
  Confluence-style docs** as the preferred — and default — external
  tools. `gh` issue access remains available as an opt-in fallback.
- **`grill-me`** (vendored from
  [mattpocock/skills](https://github.com/mattpocock/skills/tree/main/grill-me))
  and **`grill-yourself`** (native pre-flight self-interrogation) are
  first-class members of the catalog. `grill-yourself` auto-fires as a
  `/flow:finish` gate on changes that exceed a configurable diff-size
  threshold.

Read the full picture in
[`specs/001-foundation/spec.md`](./specs/001-foundation/spec.md) and the
[Phase 1 plan artifacts](./specs/001-foundation/) (`plan.md`,
`research.md`, `data-model.md`, `contracts/`, `quickstart.md`,
`tasks.md`).

## First run

Once v0.1.0 lands, the intended quickstart is:

```bash
git clone https://github.com/cooneycw/agent-power-pack.git
cd agent-power-pack
uv sync
make mcp-up                      # single container + aws secrets sidecar
make install RUNTIME=claude      # or RUNTIME=codex
```

See [`specs/001-foundation/quickstart.md`](./specs/001-foundation/quickstart.md)
for the full 9-step walkthrough.

## Dogfooding loop — how this project builds itself

agent-power-pack is built with the same tooling it ships. Every
contributor (including future-you) works an issue through this loop:

```text
  ┌─────────────────────────────────────────────────────────┐
  │  1. Pick an issue from the GitHub issue tracker         │
  │     (labels: us1-us6, phase-N, p1/p2, parallel)         │
  └────────────────────────┬────────────────────────────────┘
                           ↓
  ┌─────────────────────────────────────────────────────────┐
  │  2. grill-yourself on the task description              │
  │     (auto, or manual for small issues)                  │
  │     — surface assumptions before writing code           │
  └────────────────────────┬────────────────────────────────┘
                           ↓
  ┌─────────────────────────────────────────────────────────┐
  │  3. /flow:start <issue-number>  (once US1 lands)        │
  │     — worktree + branch off main                        │
  └────────────────────────┬────────────────────────────────┘
                           ↓
  ┌─────────────────────────────────────────────────────────┐
  │  4. Implement against the file paths named in the       │
  │     issue body (tasks.md is the authoritative source)   │
  └────────────────────────┬────────────────────────────────┘
                           ↓
  ┌─────────────────────────────────────────────────────────┐
  │  5. /second-opinion:start (once US3 lands)              │
  │     — external LLM review via second-opinion MCP        │
  └────────────────────────┬────────────────────────────────┘
                           ↓
  ┌─────────────────────────────────────────────────────────┐
  │  6. /flow:finish                                         │
  │     — runs agents-md:lint, make verify, grill-yourself  │
  │       gate if diff > thresholds, opens the PR           │
  └────────────────────────┬────────────────────────────────┘
                           ↓
  ┌─────────────────────────────────────────────────────────┐
  │  7. Merge → gh issue close <N>                          │
  └─────────────────────────────────────────────────────────┘
```

### Dogfood gates by phase

No feature is "done" until the foundation repo **itself** uses it:

| After phase | Dogfood gate |
|---|---|
| **Phase 3 (US1)** — Adapters | `make install RUNTIME=claude` installs the in-repo manifests into `.claude/skills/` so contributors use the catalog they're building. |
| **Phase 4 (US2)** — AGENTS.md lint | `.pre-commit-config.yaml` runs `agent-power-pack lint agents-md`; PRs that break the lint cannot merge. |
| **Phase 5 (US3)** — MCP container | `.woodpecker.yml` invokes the in-repo `second-opinion` MCP tool on every PR for automated review. |
| **Phase 6 (US4)** — `grill-yourself` gate | All `grill-yourself: skip` overrides are removed from the foundation PR; the real gate fires on itself. |
| **Phase 8 (US6)** — Plane + Wiki.js defaults | `project:init` is used on this repo to configure Plane + Wiki.js; open GH issues sync to Plane via `/spec:sync`; plan artifacts publish to Wiki.js automatically. |
| **Phase 9** — Woodpecker checklist | `.woodpecker.yml` passes `cicd:woodpecker-checklist` in validator mode; failing the checklist blocks the CI from finalizing. |

### What you can do TODAY (day 1 of implementation)

Even before any of the in-repo tooling exists, you can dogfood with
three things you already have:

1. **spec-kit itself.** Every non-trivial change starts with
   `/speckit-specify` in a new `specs/00N-<slug>/` directory, not direct
   edits. The `001-foundation` spec is the example to follow.
2. **`grill-me` and `grill-yourself` skills installed under
   `~/.claude/skills/`.** Both are available immediately for any
   Claude Code session working in this repo. Invoke `grill-me` when you
   want to be interviewed; `grill-yourself` fires automatically (or on
   request) before any non-trivial task. These are the same skills this
   project will vendor (`grill-me`) and author (`grill-yourself`) —
   you're grilling in the same style that Phase 6 and Phase 7 codify.
3. **`claude-power-pack` installed globally (optional).** If you have
   it, the `/flow:start`, `/flow:check`, `/flow:finish`, and
   `/second-opinion:start` commands work TODAY with this repo as the
   target. That's the truest dogfood: the predecessor building the
   successor.

## Project layout

```text
agent-power-pack/
├── AGENTS.md                   # Canonical instructions (Principle II)
├── CLAUDE.md / GEMINI.md       # GENERATED from AGENTS.md
├── .cursorrules                # GENERATED from AGENTS.md
├── ATTRIBUTION.md              # Vendored-skill credits (Principle V)
├── manifests/                  # Neutral YAML skill catalog (Principle I)
├── adapters/                   # Per-runtime transpilers
├── src/agent_power_pack/       # Linter, generator, project:init, grill, secrets, cicd
├── mcp_container/              # Single multi-transport MCP container (Principle III)
├── vendor/skills/              # Pinned third-party skills (e.g. grill-me)
├── specs/001-foundation/       # Spec-kit artifacts for the foundation feature
└── tests/                      # unit / integration / e2e / perf
```

## Contributing

See [`CONTRIBUTING.md`](./CONTRIBUTING.md) (lands with T112). TL;DR:

1. Every change starts with a spec-kit spec.
2. Every skill must list all first-class runtimes in its manifest
   (Principle I); the validator rejects partial coverage.
3. Every PR that exceeds the `grill-yourself` diff thresholds must have
   a `grill-yourself` transcript attached.
4. `AGENTS.md` is hand-edited; `CLAUDE.md`, `GEMINI.md`, and
   `.cursorrules` are not.

## License

MIT. See [`LICENSE`](./LICENSE).
