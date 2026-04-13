# Runtime Invocation Matrix

**Status**: Normative — all specs and docs MUST reference this matrix for
runtime-specific invocation patterns instead of assuming a single invocation
shape.

## Purpose

Skills in agent-power-pack are authored once as neutral YAML manifests and
transpiled per runtime. Each runtime has a distinct invocation model. This
matrix is the single source of truth for how each skill family is invoked
on each supported runtime.

When specs, docs, or acceptance scenarios reference a skill, they MUST use
the **conceptual skill name** in backticks (e.g., `agents-md:lint`) without
a leading `/` or any other runtime-specific prefix. For runtime-specific
invocation, reference this matrix.

## Invocation Models by Runtime

| Runtime | Invocation Model | Skill Discovery |
|---------|-----------------|-----------------|
| **Claude Code** | Slash-command palette (`/skill:action`) or natural language | `.claude/skills/*/SKILL.md` |
| **Codex CLI** | Natural language prompt referencing the skill, or `@skill-name` mention | `.agents/skills/*/SKILL.md` (repo-scoped) |
| **Gemini CLI** | Natural language prompt (adapter TBD before v1.0.0) | `.gemini/` layout (TBD) |
| **Cursor** | Natural language prompt (adapter TBD before v1.0.0) | `.cursorrules` + `.cursor/skills/` (TBD) |

## Per-Family Invocation Examples

The table below shows representative invocations for each skill family on
Claude Code and Codex CLI (the two first-class runtimes at v0.1.0). Gemini
CLI and Cursor patterns will be added when those adapters ship.

| Conceptual Skill | Claude Code | Codex CLI |
|-----------------|-------------|-----------|
| `agents-md:lint` | `/agents-md:lint` | "run the agents-md lint" or `agent-power-pack lint agents-md` |
| `flow:start N` | `/flow:start 42` | "start flow for issue 42" or `agent-power-pack flow start 42` |
| `flow:finish` | `/flow:finish` | "finish the current flow" or `agent-power-pack flow finish` |
| `flow:check` | `/flow:check` | "run flow check" or `agent-power-pack flow check` |
| `flow:auto N` | `/flow:auto 42` | "run flow auto for issue 42" or `agent-power-pack flow auto 42` |
| `grill:me` | `/grill:me` or "grill me on this plan" | "grill me on this plan" |
| `grill:yourself` | `/grill:yourself` | "grill yourself on this plan" or `agent-power-pack grill yourself` |
| `spec:create` | `/spec:create` | "create a new spec" |
| `spec:sync` | `/spec:sync` | "sync specs to Plane and Wiki.js" |
| `issue:create` | `/issue:create` | "create an issue in Plane" |
| `docs:c4` | `/docs:c4` | "generate C4 diagrams" |
| `security:scan` | `/security:scan` | "run a security scan" |
| `secrets:get KEY` | `/secrets:get KEY` | "get secret KEY" |
| `project:init` | `/project:init` | `agent-power-pack init` |
| `project:lite` | `/project:lite name` | `agent-power-pack init --lite name` |
| `project:next` | `/project:next` | "what issue should I work on next" |
| `second-opinion:start` | `/second-opinion:start` | "get a second opinion on this" |

### CLI Invocations (Runtime-Neutral)

All skills that have a CLI counterpart can also be invoked directly via the
`agent-power-pack` CLI, regardless of runtime:

```bash
agent-power-pack lint agents-md          # agents-md:lint
agent-power-pack flow start 42           # flow:start
agent-power-pack flow finish             # flow:finish
agent-power-pack grill yourself          # grill:yourself
agent-power-pack init                    # project:init
agent-power-pack init --lite my-project  # project:lite
```

These CLI invocations are the same on every runtime and are the recommended
form for acceptance scenarios in specs.

## Guidelines for Spec Authors

1. **Use the conceptual skill name** in backticks: `flow:finish`, not
   `/flow:finish`.
2. **Reference the CLI form** in acceptance scenarios where possible:
   `agent-power-pack flow finish`, not `/flow:finish`.
3. **When showing runtime-specific examples**, show at least Claude Code
   and Codex CLI side by side, referencing this matrix for the full set.
4. **Never assume slash commands are available** on all runtimes. Slash
   commands are a Claude Code UX feature, not a universal interface.
5. **For acceptance scenarios**, prefer the CLI form or state "invoke the
   `skill:action` skill (see Runtime Invocation Matrix)" rather than
   hard-coding a single runtime's syntax.
