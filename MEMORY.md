# Project Memory

Key decisions, trade-offs, and context for agent-power-pack that are not
obvious from the code or git history alone.

## v0.1.0 Foundation Release (2026-04-13)

### Origin and Motivation

agent-power-pack unifies two predecessor repos — `cooneycw/claude-power-pack`
and `cooneycw/codex-power-pack` — into a single, runtime-neutral power pack.
The split was untenable: every skill addition required parallel edits in both
repos with diverging conventions. The decision to merge was driven by the
emergence of AGENTS.md as a cross-agent standard and the desire to support
Gemini CLI and Cursor without creating yet more forks.

### Key Architectural Decisions

- **Neutral YAML manifests over per-runtime skill files.** Skills are authored
  once in `manifests/<family>/<skill>.yaml` and transpiled at install time.
  This was chosen over a shared-library approach because runtime skill formats
  differ too much for a single source file to work everywhere.

- **AGENTS.md as canonical, generated runtime files.** CLAUDE.md, GEMINI.md,
  and .cursorrules are generated outputs, not hand-edited. This eliminates
  drift between runtimes and makes the linter a hard gate rather than advisory.

- **Single MCP container, multi-transport.** All six MCP servers share one
  Docker image with per-port protocol selection. This was chosen over
  per-server containers to simplify deployment and reduce resource usage for
  solo operators. The trade-off is a larger image and coupled release cycles.

- **`grill-yourself` replaces `sequential-thinking`.** The old
  sequential-thinking skill was a generic chain-of-thought wrapper. The new
  grill-yourself skill is purpose-built for pre-flight assumption surfacing
  with diff-size triggers and transcript logging.

- **Tiered secrets: dotenv -> env-file -> AWS Secrets Manager.** Local dev
  uses .env files; production uses the Rust-based aws-secretsmanager-agent
  sidecar. The tier resolution is automatic based on what's available, with
  no configuration required for the simplest case.

- **Plane over GitHub Issues, Wiki.js over Confluence.** Self-hostable,
  open-source tools are preferred. GitHub Issues remains as an opt-in fallback
  adapter (spec FR-010) but is not the default path.

### Removed from Predecessors

- `sequential-thinking` — superseded by `grill-yourself`.
- `docs:pptx` (PowerPoint export) — deliverable surface is Wiki.js, not
  slide decks.

### Known Limitations at v0.1.0

- Gemini CLI and Cursor adapters are stubs; full parity is a v1.0.0 target.
- MCP container health checks require Docker running locally; no remote
  registry or hosted deployment yet.
- The `docs:auto` pipeline (spec 002) is in early stages — `docs:start` and
  `docs:analyze` skills are present but the full DAG-based generation is not
  yet wired end-to-end.
