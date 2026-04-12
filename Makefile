.PHONY: install mcp-up mcp-down mcp-health verify lint test update-vendored-skills secrets-sidecar-up

install:
ifndef RUNTIME
	$(error RUNTIME is required. Usage: make install RUNTIME=claude-code)
endif
	agent-power-pack install $(RUNTIME) --target-dir "$(CURDIR)" --manifests "$(CURDIR)/manifests"

mcp-up:
	docker compose up -d mcp secrets-sidecar

mcp-down:
	docker compose down

mcp-health:
	@for port in 8080 8081 8082 8083 8084 8085; do \
		curl -sf http://localhost:$$port/healthz || echo "FAIL: port $$port"; \
	done

verify:
	@echo "TODO: ruff check + mypy + pytest -m 'unit or integration' + perf"

lint:
	@echo "TODO: ruff check + mypy + agent-power-pack lint agents-md --json"

test:
	@echo "TODO: pytest"

update-vendored-skills:
	@echo "TODO: scripts/update_vendored_skills.py"

secrets-sidecar-up:
	docker compose up -d secrets-sidecar
