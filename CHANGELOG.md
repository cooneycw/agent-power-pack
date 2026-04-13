# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog, and this project follows Semantic
Versioning once it reaches `1.0.0`.

## [0.1.0] - 2026-04-13

First foundation release unifying `claude-power-pack` and `codex-power-pack`
into a single, runtime-neutral agentic power pack.

### Added

- **Manifest system** (Phase 2): neutral YAML skill catalog with 61 manifests
  across 13 families — flow, spec, CI/CD, security, QA, agents-md, issue,
  wiki, project, secrets, grill, docs, and second-opinion
- **Runtime adapters** (Phase 3): Claude Code and Codex CLI adapters with
  workspace-wide installation (`make install RUNTIME=<x>`); Gemini CLI and
  Cursor adapter stubs for v1.0.0
- **AGENTS.md linter** (Phase 4): offline, deterministic quality gate
  verifying required sections, Make target existence, and generated-file
  freshness; regenerates CLAUDE.md, GEMINI.md, and .cursorrules from
  AGENTS.md on every run
- **MCP container** (Phase 5): single multi-transport Docker image hosting
  `second-opinion`, `plane`, `wikijs`, `nano-banana`, `playwright`, and
  `woodpecker` servers with HTTP (8080-8085) and streamable HTTP (9100-9105)
  ports
- **grill-yourself** (Phase 6): pre-flight self-interrogation skill with
  diff-size triggers (configurable via `.specify/grill-triggers.yaml`),
  transcript logging, and `/flow:finish` gate integration
- **grill-me** (Phase 7): vendored from `mattpocock/skills` with full
  attribution preserved in ATTRIBUTION.md and the skill manifest
- **`project:init` wizard** (Phase 8): guided bootstrap for Plane and
  Wiki.js with connectivity probes, AWS sidecar health checks, and
  automatic AGENTS.md updates
- **Woodpecker checklist validator** (Phase 9): CI pipeline validation
  against best-practice checklist
- **Tiered secrets** layer: dotenv -> env-file -> AWS Secrets Manager via
  the Rust-based `aws-secretsmanager-agent` sidecar
- **Codex CLI smoke tests**: runtime compatibility verification ensuring
  generated artifacts are consumable by the real `codex` binary
- **docs:start and docs:analyze** skills (spec 002): early documentation
  pipeline with Wiki.js convention templates and theme inference
- **docs:auto** skill: multi-model DAG-based document generation pipeline
- Root project policy files: LICENSE (MIT), ATTRIBUTION.md,
  CONTRIBUTING.md, SECURITY.md, CODE_OF_CONDUCT.md
- Woodpecker CI pipeline configuration (`.woodpecker.yml`)
- Constitution v0.1.0 ratified with five core principles

### Changed

- Replaced placeholder Makefile targets with runnable `make lint`,
  `make test`, and `make verify` commands
- Namespaced skill directories as `{family}-{name}` to prevent
  cross-family collisions
- Replaced stale SSE terminology with streamable HTTP for Codex ports

### Removed

- `sequential-thinking` skill — superseded by `grill-yourself`
- `docs:pptx` (PowerPoint export) — deliverable surface is Wiki.js
