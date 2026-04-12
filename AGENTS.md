# AGENTS.md

Canonical instruction file for agent-power-pack. All runtime-specific files
(CLAUDE.md, GEMINI.md, .cursorrules) are generated from this document.

## CI/CD Protocol

All CI runs through Make targets. The current pipeline stubs are defined in the
Makefile and will be wired to Woodpecker CI as the project matures.

- `make verify` — run ruff, mypy, and the test suite
- `make lint` — run ruff check, mypy, and agents-md linter
- `make test` — run pytest

## Quality Gates

Before merging any PR, the following must pass:

1. `make lint` exits 0 (includes `agents-md:lint`)
2. `make test` exits 0
3. `make verify` exits 0
4. No ruff or mypy errors

## Troubleshooting

- If `make install` fails with "RUNTIME is required", pass the runtime:
  `make install RUNTIME=claude-code`
- If MCP container health checks fail, ensure Docker is running and ports
  8080-8085 are free.
- If `make mcp-up` fails, check that `compose.yaml` is present and
  `docker compose` is available.

## Available Commands

| Command | Description |
|---|---|
| `make install` | Install skill catalog for a given runtime |
| `make mcp-up` | Start MCP container and secrets sidecar |
| `make mcp-down` | Stop all containers |
| `make mcp-health` | Health-check MCP server ports |
| `make verify` | Run full verification suite |
| `make lint` | Run linters |
| `make test` | Run test suite |
| `make update-vendored-skills` | Update vendored skill files |
| `make secrets-sidecar-up` | Start the AWS secrets sidecar |

## Docker Conventions

Services are defined in `compose.yaml`:

- `docker compose up -d mcp` — start the MCP container
- `docker compose up -d secrets-sidecar` — start the AWS secrets sidecar
- `docker compose down` — stop all services

All containers join the `mcp-net` bridge network. The MCP container exposes
ports 8080-8085 (HTTP) and 9100-9105 (SSE).

## Deployment

Deployment is local-first via Docker Compose. Production deployment documentation
will be added when the project reaches that stage. For now:

1. Copy `.env.example` to `.env` and fill in secrets
2. Run `make mcp-up`
3. Verify with `make mcp-health`
