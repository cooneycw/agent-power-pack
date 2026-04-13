# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog, and this project follows Semantic
Versioning once it reaches `1.0.0`.

## [0.1.0] - 2026-04-13

### Added

- Neutral YAML manifest catalog spanning flow, spec, CI/CD, security, QA,
  agents-md, issue, wiki, project, secrets, and grill workflows
- Runtime adapters for Claude Code and Codex CLI plus Gemini CLI and Cursor
  stubs for workspace-wide installation flow
- `project:init` wizard for Plane and Wiki.js bootstrap with probes and AGENTS.md
  updates
- Multi-server MCP container shipping `second-opinion`, `plane`, `wikijs`,
  `nano-banana`, `playwright`, and `woodpecker`
- AGENTS.md linting, Woodpecker checklist validation, grill-yourself transcript
  generation, and tiered secrets backends

### Changed

- Promoted the package and documentation set to the first tagged foundation
  release
- Replaced placeholder local verification targets with runnable `make lint`,
  `make test`, and `make verify` commands
- Added root project policy files and Woodpecker pipeline configuration for
  contributor and CI readiness
