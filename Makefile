.PHONY: install mcp-up mcp-down mcp-health verify lint test update-vendored-skills secrets-sidecar-up

install:
	@echo "TODO: agent-power-pack install --runtime $(RUNTIME)"

mcp-up:
	@echo "TODO: docker compose up -d mcp"

mcp-down:
	@echo "TODO: docker compose down"

mcp-health:
	@echo "TODO: check MCP server health endpoints"

verify:
	@echo "TODO: ruff check + mypy + pytest -m 'unit or integration' + perf"

lint:
	@echo "TODO: ruff check + mypy + agent-power-pack lint agents-md --json"

test:
	@echo "TODO: pytest"

update-vendored-skills:
	@echo "TODO: scripts/update_vendored_skills.py"

secrets-sidecar-up:
	@echo "TODO: docker compose up -d secrets-sidecar"
