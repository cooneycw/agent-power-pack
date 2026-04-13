# Contributing to agent-power-pack

Thank you for your interest in contributing. This document explains the
workflow, rules, and gates that every change must pass.

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) for workspace management
- Docker (for MCP container and secrets sidecar)
- [Claude Code](https://claude.ai/code), [Codex CLI](https://github.com/openai/codex),
  or another supported runtime

```bash
git clone https://github.com/cooneycw/agent-power-pack.git
cd agent-power-pack
uv sync
```

## The spec-kit workflow

Every non-trivial change starts with a specification, not code.

1. **Specify** — create a spec under `.specify/specs/<NNN>-<slug>/spec.md`
   using `/spec:create` or manually. The spec must include a problem
   statement, user stories, acceptance criteria, and non-goals.
2. **Plan** — produce a `plan.md` in the same directory with file paths,
   data models, and task breakdown.
3. **Implement** — work the tasks from `tasks.md`, one issue at a time.
4. **Ship** — PR, review, merge.

The [Constitution](.specify/memory/constitution.md) governs all design
decisions. When in doubt, check the constitution.

## The manifest-first rule

Skills are authored as **neutral YAML manifests** under `manifests/<family>/<name>.yaml`,
never as runtime-specific files. The manifest schema is defined in
`src/agent_power_pack/manifest/schema.py` and enforced by the validator.

Every manifest must:

- Declare **all four first-class runtimes**: `claude-code`, `codex-cli`,
  `gemini-cli`, `cursor`. The validator rejects partial coverage.
- Reference only known MCP servers (`second-opinion`, `plane`, `wikijs`,
  `nano-banana`, `playwright`, `woodpecker`).
- Use a `family` from the fixed set (`flow`, `spec`, `cicd`, `docs`,
  `security`, `secrets`, `qa`, `agents-md`, `second-opinion`, `issue`,
  `wiki`, `project`, `grill`).

Runtime-specific instruction files (`CLAUDE.md`, `GEMINI.md`,
`.cursorrules`) are **generated** from `AGENTS.md` — never hand-edited.

## The grill gate

PRs that exceed the diff-size thresholds in `.specify/grill-triggers.yaml`
(default: 200 lines changed or 5 files) must include a `grill-yourself`
transcript. The `/flow:finish` command enforces this automatically.

To run manually:

```bash
agent-power-pack grill yourself --plan "description of your change"
```

Attach the transcript to the PR body. A PR without a required transcript
will be blocked.

You can also request a `grill-me` session where the AI interviews you
about your design decisions — useful for complex architectural changes.

## AGENTS.md is canonical

`AGENTS.md` at the repo root is the single source of truth for project
instructions. It must contain these six required sections:

1. `## CI/CD Protocol`
2. `## Quality Gates`
3. `## Troubleshooting`
4. `## Available Commands`
5. `## Docker Conventions`
6. `## Deployment`

The `agents-md:lint` skill validates this. Run it with:

```bash
agent-power-pack lint agents-md
```

## Development workflow

```bash
# Install dependencies
uv sync

# Run linter
make lint

# Run tests
make test

# Run full verification (lint + test + perf)
make verify

# Start MCP container
make mcp-up

# Install skills into your runtime
make install RUNTIME=claude-code
```

## Pull request checklist

- [ ] Change starts from a spec (or is trivially small)
- [ ] New skills are YAML manifests, not runtime-specific files
- [ ] All four runtimes listed in manifest `runtimes` field
- [ ] `make lint` passes
- [ ] `make test` passes
- [ ] `grill-yourself` transcript attached (if diff exceeds thresholds)
- [ ] `AGENTS.md` updated if commands or conventions changed
- [ ] No hand-edits to `CLAUDE.md`, `GEMINI.md`, or `.cursorrules`

## Code style

- Python: enforced by `ruff` (line length 100, target Python 3.11)
- Type checking: `mypy --strict`
- Tests: `pytest` with markers (`unit`, `integration`, `e2e`, `perf`)

## License

By contributing, you agree that your contributions will be licensed
under the MIT License.
