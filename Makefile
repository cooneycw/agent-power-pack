.PHONY: install mcp-up mcp-down mcp-health verify lint test test-codex-smoke update-vendored-skills secrets-sidecar-up

install:
ifndef RUNTIME
	$(error RUNTIME is required. Usage: make install RUNTIME=claude-code)
endif
	uv run agent-power-pack install $(RUNTIME) --target-dir "$(CURDIR)" --manifests "$(CURDIR)/manifests"

mcp-up:
	docker compose up -d mcp secrets-sidecar

mcp-down:
	docker compose down

mcp-health:
	@for port in 8080 8081 8082 8083 8084 8085; do \
		curl -sf http://localhost:$$port/healthz || echo "FAIL: port $$port"; \
	done

verify:
	uv run ruff check .
	uv run mypy src tests
	uv run pytest -m "unit or integration"
	uv run pytest -m perf

lint:
	uv run ruff check .
	uv run mypy src tests
	uv run agent-power-pack lint agents-md

test:
	uv run pytest

test-codex-smoke:
	uv run pytest -m codex_smoke -v

update-vendored-skills:
	python scripts/update_vendored_skills.py

secrets-sidecar-up:
	docker compose up -d secrets-sidecar
