# Quickstart — Agent Power Pack Foundation

First-run walkthrough for a developer bringing agent-power-pack up on a
fresh machine. Mirrors the acceptance flow used by
`tests/e2e/test_dual_attach.py` and `tests/integration/test_app_init_wizard.py`.

## Prerequisites

- Python 3.11 or later
- [`uv`](https://docs.astral.sh/uv/) 0.11+
- Docker Engine 24+ with Compose v2
- `git`
- A reachable Plane instance and Wiki.js instance (or `--skip` both
  during `app:init`)
- At least one AI agent runtime installed:
  - Claude Code CLI, **or**
  - Codex CLI, **or**
  - both (this is the main user story)

## 1. Clone and bootstrap

```bash
git clone https://github.com/cooneycw/agent-power-pack.git
cd agent-power-pack
uv sync
```

`uv sync` installs every component of the workspace (`adapters/`,
`src/agent_power_pack/`, `mcp_container/` Python code, test deps) into
a single `.venv/`.

## 2. Configure secrets (tiered)

Development default is `dotenv`. Copy the example and fill in at least
the second-opinion backend keys you plan to use:

```bash
cp .env.example .env
$EDITOR .env
```

For production, start the AWS Secrets Manager sidecar instead:

```bash
make secrets-sidecar-up     # starts the Rust aws-secretsmanager-agent container
```

Once the sidecar is healthy, the tiered secrets layer automatically
prefers it over `.env`.

## 3. Bring up the MCP container

```bash
make mcp-up
```

This builds (or pulls) the single MCP container image and starts all six
servers plus the secrets sidecar via `compose.yaml`. Expected cold-start
budget: **< 15 seconds** to all-six-healthy.

Verify:

```bash
make mcp-health
# → second-opinion: healthy
# → plane:          healthy
# → wikijs:         healthy
# → nano-banana:    healthy
# → playwright:     healthy
# → woodpecker:     healthy
```

## 4. Install the skill catalog on your runtime(s)

### Claude Code

```bash
make install RUNTIME=claude
```

Produces `.claude/skills/*/SKILL.md` files. Open this directory in Claude
Code and the skills appear in the slash-command palette.

### Codex CLI

```bash
make install RUNTIME=codex
```

Produces `.codex/skills/` and merges MCP server registrations into
`~/.codex/config.toml`. Open a Codex CLI session in this directory and
the skills appear as `$apppack-*` style prompt triggers.

### Both concurrently

Run the two install commands in any order. Both adapters are idempotent
and stay in their own runtime directories (Principle III enforcement in
the adapter interface contract).

## 5. Bootstrap a NEW project with `app:init`

From another directory:

```bash
mkdir ~/my-project && cd ~/my-project
agent-power-pack init
```

The wizard:

1. Scaffolds `AGENTS.md` from the starter template.
2. Generates `CLAUDE.md`, `GEMINI.md`, `.cursorrules` from it.
3. Writes a starter `Makefile` + `compose.yaml`.
4. Prompts for Plane base URL, workspace slug, and API token (or
   `--skip`).
5. Prompts for Wiki.js base URL, space, and API token (or `--skip`).
6. Runs a one-shot connectivity check against each configured tool.
7. Records configured endpoints in an `External Systems` section in the
   new `AGENTS.md`.

Skipped tools can be revisited later:

```bash
agent-power-pack init --reconfigure plane
agent-power-pack init --reconfigure wikijs
```

## 6. Verify the AGENTS.md lint gate

Intentionally break it to confirm the gate works:

```bash
echo "See \`make nonexistent-target\` for details." >> AGENTS.md
agent-power-pack lint agents-md
# → FAIL: repo.make_target_exists — missing target: nonexistent-target
```

Fix it:

```bash
# (either add the target to the Makefile, or revert AGENTS.md)
agent-power-pack lint agents-md
# → PASS
```

The lint gate also regenerates `CLAUDE.md` / `GEMINI.md` / `.cursorrules`
when `AGENTS.md` changes, and reverts any hand-edits to those generated
files.

## 7. Try grill-me (interactive)

From an installed runtime session:

> `grill me on this plan` (Claude Code)
> `$apppack-grill-me` (Codex CLI)

Walk through the Q&A loop. The underlying skill is vendored from
[mattpocock/skills](https://github.com/mattpocock/skills/tree/main/grill-me)
with attribution preserved in `ATTRIBUTION.md`.

## 8. Try grill-yourself as a flow gate

Make a change large enough to trip the diff-size threshold (default
`>200 lines` OR `>5 files`):

```bash
# ...edit several files...
git add -A && git commit -m "big refactor"
agent-power-pack flow finish
```

`grill-yourself` fires automatically, generates pre-flight questions,
answers them, and attaches the transcript to your PR under
`.specify/grills/<timestamp>.md`.

Override with a commit trailer when you want to skip:

```bash
git commit -m "big refactor

grill-yourself: skip"
```

## 9. Run the test suite

```bash
make verify
```

Runs `pytest` across unit, integration, and e2e. The e2e suite spins
real MCP containers via `testcontainers`, so Docker must be running.

## Troubleshooting

- **`make install RUNTIME=gemini` fails with `AdapterNotImplemented`** —
  expected for v0.1.0. Gemini and Cursor adapters land before v1.0.0
  (see spec FR-002).
- **`make mcp-up` exceeds the 15s cold-start budget** — the first build
  can take several minutes because it pulls the Playwright Jammy base
  image (~1.5 GB). The 15s budget applies to warm starts only.
- **`app:init` connectivity check fails for Plane** — the wizard
  prints the HTTP status and first 200 bytes of the response. Most
  common cause: wrong workspace slug. Re-run with `--reconfigure plane`.
- **`agents-md:lint` reports a generated file is out of sync after a
  manual `AGENTS.md` edit** — this is correct. Run
  `agent-power-pack generate` to regenerate, or let `/flow:check`
  handle it automatically.
