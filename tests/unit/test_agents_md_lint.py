"""Unit tests for AGENTS.md linter — Phase 4 (T044).

Tests every rule ID:
- schema.required_section
- repo.make_target_exists
- repo.docker_service_exists
- repo.ci_file_exists
- generated.in_sync / generated.header_present
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from agent_power_pack.linter.document import load_agents_md
from agent_power_pack.linter.generated_check import GENERATED_HEADER, HASH_PREFIX, check_generated
from agent_power_pack.linter.repo_check import check_repo
from agent_power_pack.linter.result import LintCheck
from agent_power_pack.linter.schema_check import check_schema
from agent_power_pack.linter.agents_md import lint_agents_md
from agent_power_pack.generator.instruction_files import generate_instruction_files
from agent_power_pack.generator.revert import revert_hand_edits

FULL_AGENTS_MD = """\
# AGENTS.md

## CI/CD Protocol

Use `make test` to run tests.

## Quality Gates

All tests must pass.

## Troubleshooting

Check the logs.

## Available Commands

| Command | Description |
|---|---|
| `make install` | Install |
| `make lint` | Lint |

## Docker Conventions

Run `docker compose up -d mcp` to start.

## Deployment

Deploy with Docker Compose.
"""

MINIMAL_AGENTS_MD = """\
# AGENTS.md

## CI/CD Protocol

Run CI.
"""


def _content_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


# ── schema.required_section ──────────────────────────────────────────


@pytest.mark.unit
class TestSchemaCheck:
    def test_all_sections_present(self, tmp_path: Path) -> None:
        agents = tmp_path / "AGENTS.md"
        agents.write_text(FULL_AGENTS_MD)
        doc = load_agents_md(agents)
        checks = check_schema(doc)

        # 6 per-section checks + 1 overall
        assert len(checks) == 7
        assert all(c.status == "pass" for c in checks)
        assert all(c.rule_id == "schema.required_section" for c in checks)

    def test_missing_section(self, tmp_path: Path) -> None:
        agents = tmp_path / "AGENTS.md"
        agents.write_text(MINIMAL_AGENTS_MD)
        doc = load_agents_md(agents)
        checks = check_schema(doc)

        assert len(checks) == 7
        failed = [c for c in checks if c.status == "fail"]
        # 5 missing sections + 1 overall
        assert len(failed) == 6

        # The one present section should pass
        passed = [c for c in checks if c.status == "pass"]
        assert len(passed) == 1
        assert passed[0].subject == "CI/CD Protocol"


# ── repo.make_target_exists ──────────────────────────────────────────


@pytest.mark.unit
class TestRepoMakeTargets:
    def test_valid_targets(self, tmp_path: Path) -> None:
        agents = tmp_path / "AGENTS.md"
        agents.write_text("## Available Commands\n\n`make install`\n`make lint`\n")
        makefile = tmp_path / "Makefile"
        makefile.write_text("install:\n\t@echo ok\n\nlint:\n\t@echo ok\n")

        doc = load_agents_md(agents)
        checks = check_repo(doc, tmp_path)

        target_checks = [c for c in checks if c.rule_id == "repo.make_target_exists"]
        assert len(target_checks) == 2
        assert all(c.status == "pass" for c in target_checks)

    def test_missing_target(self, tmp_path: Path) -> None:
        agents = tmp_path / "AGENTS.md"
        agents.write_text("## Commands\n\n`make install`\n`make bogus`\n")
        makefile = tmp_path / "Makefile"
        makefile.write_text("install:\n\t@echo ok\n")

        doc = load_agents_md(agents)
        checks = check_repo(doc, tmp_path)

        target_checks = [c for c in checks if c.rule_id == "repo.make_target_exists"]
        assert len(target_checks) == 2
        passed = [c for c in target_checks if c.status == "pass"]
        failed = [c for c in target_checks if c.status == "fail"]
        assert len(passed) == 1
        assert passed[0].subject == "install"
        assert len(failed) == 1
        assert failed[0].subject == "bogus"

    def test_no_makefile_warns(self, tmp_path: Path) -> None:
        agents = tmp_path / "AGENTS.md"
        agents.write_text("`make install`\n`make lint`\n")

        doc = load_agents_md(agents)
        checks = check_repo(doc, tmp_path)

        target_checks = [c for c in checks if c.rule_id == "repo.make_target_exists"]
        assert len(target_checks) == 2
        assert all(c.status == "warn" for c in target_checks)


# ── repo.docker_service_exists ───────────────────────────────────────


@pytest.mark.unit
class TestRepoDockerServices:
    def test_valid_service(self, tmp_path: Path) -> None:
        agents = tmp_path / "AGENTS.md"
        agents.write_text("`docker compose up -d mcp`\n")
        compose = tmp_path / "compose.yaml"
        compose.write_text("services:\n  mcp:\n    image: test\n")

        doc = load_agents_md(agents)
        checks = check_repo(doc, tmp_path)

        svc_checks = [c for c in checks if c.rule_id == "repo.docker_service_exists"]
        assert len(svc_checks) == 1
        assert svc_checks[0].status == "pass"

    def test_missing_service(self, tmp_path: Path) -> None:
        agents = tmp_path / "AGENTS.md"
        agents.write_text("`docker compose up -d missing-svc`\n")
        compose = tmp_path / "compose.yaml"
        compose.write_text("services:\n  mcp:\n    image: test\n")

        doc = load_agents_md(agents)
        checks = check_repo(doc, tmp_path)

        svc_checks = [c for c in checks if c.rule_id == "repo.docker_service_exists"]
        assert len(svc_checks) == 1
        assert svc_checks[0].status == "fail"

    def test_no_compose_skips(self, tmp_path: Path) -> None:
        agents = tmp_path / "AGENTS.md"
        agents.write_text("`docker compose up -d mcp`\n")

        doc = load_agents_md(agents)
        checks = check_repo(doc, tmp_path)

        svc_checks = [c for c in checks if c.rule_id == "repo.docker_service_exists"]
        assert len(svc_checks) == 0


# ── repo.ci_file_exists ─────────────────────────────────────────────


@pytest.mark.unit
class TestRepoCiFiles:
    def test_existing_ci_file(self, tmp_path: Path) -> None:
        agents = tmp_path / "AGENTS.md"
        agents.write_text("CI config at `.woodpecker.yml`\n")
        (tmp_path / ".woodpecker.yml").write_text("pipeline:\n")

        doc = load_agents_md(agents)
        checks = check_repo(doc, tmp_path)

        ci_checks = [c for c in checks if c.rule_id == "repo.ci_file_exists"]
        assert len(ci_checks) == 1
        assert ci_checks[0].status == "pass"

    def test_missing_ci_file(self, tmp_path: Path) -> None:
        agents = tmp_path / "AGENTS.md"
        agents.write_text("CI config at `.woodpecker.yml`\n")

        doc = load_agents_md(agents)
        checks = check_repo(doc, tmp_path)

        ci_checks = [c for c in checks if c.rule_id == "repo.ci_file_exists"]
        assert len(ci_checks) == 1
        assert ci_checks[0].status == "fail"


# ── generated.in_sync / generated.header_present ────────────────────


@pytest.mark.unit
class TestGeneratedCheck:
    def test_fresh_generated_file(self, tmp_path: Path) -> None:
        agents = tmp_path / "AGENTS.md"
        agents.write_text(FULL_AGENTS_MD)
        doc = load_agents_md(agents)

        h = doc.content_hash
        claude_md = tmp_path / "CLAUDE.md"
        claude_md.write_text(f"{GENERATED_HEADER}\n{HASH_PREFIX}{h} -->\n{FULL_AGENTS_MD}")

        checks = check_generated(doc, tmp_path)
        header_checks = [c for c in checks if c.rule_id == "generated.header_present"]
        sync_checks = [c for c in checks if c.rule_id == "generated.in_sync"]

        assert len(header_checks) == 1
        assert header_checks[0].status == "pass"
        assert len(sync_checks) == 1
        assert sync_checks[0].status == "pass"

    def test_stale_generated_file(self, tmp_path: Path) -> None:
        agents = tmp_path / "AGENTS.md"
        agents.write_text(FULL_AGENTS_MD)
        doc = load_agents_md(agents)

        claude_md = tmp_path / "CLAUDE.md"
        claude_md.write_text(f"{GENERATED_HEADER}\n{HASH_PREFIX}stale-hash -->\n old content")

        checks = check_generated(doc, tmp_path)
        sync_checks = [c for c in checks if c.rule_id == "generated.in_sync"]
        assert len(sync_checks) == 1
        assert sync_checks[0].status == "fail"

    def test_hand_edited_no_header(self, tmp_path: Path) -> None:
        agents = tmp_path / "AGENTS.md"
        agents.write_text(FULL_AGENTS_MD)
        doc = load_agents_md(agents)

        claude_md = tmp_path / "CLAUDE.md"
        claude_md.write_text("# My hand-edited CLAUDE.md\n")

        checks = check_generated(doc, tmp_path)
        header_checks = [c for c in checks if c.rule_id == "generated.header_present"]
        sync_checks = [c for c in checks if c.rule_id == "generated.in_sync"]

        assert len(header_checks) == 1
        assert header_checks[0].status == "fail"
        assert len(sync_checks) == 1
        assert sync_checks[0].status == "fail"

    def test_nonexistent_generated_files_skipped(self, tmp_path: Path) -> None:
        agents = tmp_path / "AGENTS.md"
        agents.write_text(FULL_AGENTS_MD)
        doc = load_agents_md(agents)

        checks = check_generated(doc, tmp_path)
        assert len(checks) == 0


# ── Orchestrator (lint_agents_md) ────────────────────────────────────


@pytest.mark.unit
class TestOrchestrator:
    def test_missing_agents_md(self, tmp_path: Path) -> None:
        result = lint_agents_md(tmp_path)
        assert result.status == "fail"
        assert len(result.checks) == 1
        assert result.checks[0].rule_id == "schema.required_section"

    def test_full_pass(self, tmp_path: Path) -> None:
        agents = tmp_path / "AGENTS.md"
        agents.write_text(FULL_AGENTS_MD)
        makefile = tmp_path / "Makefile"
        makefile.write_text("install:\n\t@echo ok\n\nlint:\n\t@echo ok\n\ntest:\n\t@echo ok\n")

        result = lint_agents_md(tmp_path)
        assert result.status == "pass"
        assert result.duration_ms >= 0


# ── Generator ────────────────────────────────────────────────────────


@pytest.mark.unit
class TestGenerator:
    def test_generate_instruction_files(self, tmp_path: Path) -> None:
        agents = tmp_path / "AGENTS.md"
        agents.write_text(FULL_AGENTS_MD)

        written = generate_instruction_files(tmp_path)
        assert len(written) == 3

        filenames = {p.name for p in written}
        assert filenames == {"CLAUDE.md", "GEMINI.md", ".cursorrules"}

        for p in written:
            text = p.read_text()
            assert text.startswith(GENERATED_HEADER)
            lines = text.splitlines()
            assert lines[1].startswith(HASH_PREFIX)

    def test_no_agents_md(self, tmp_path: Path) -> None:
        written = generate_instruction_files(tmp_path)
        assert written == []


# ── Revert ───────────────────────────────────────────────────────────


@pytest.mark.unit
class TestRevert:
    def test_revert_hand_edited(self, tmp_path: Path) -> None:
        agents = tmp_path / "AGENTS.md"
        agents.write_text(FULL_AGENTS_MD)

        claude_md = tmp_path / "CLAUDE.md"
        claude_md.write_text("# Hand-edited content\n")

        checks = revert_hand_edits(tmp_path)
        assert len(checks) == 1
        assert checks[0].status == "warn"
        assert "reverted" in checks[0].message

        # Verify file was regenerated
        text = claude_md.read_text()
        assert text.startswith(GENERATED_HEADER)

    def test_no_revert_needed(self, tmp_path: Path) -> None:
        agents = tmp_path / "AGENTS.md"
        agents.write_text(FULL_AGENTS_MD)
        doc = load_agents_md(agents)

        claude_md = tmp_path / "CLAUDE.md"
        claude_md.write_text(
            f"{GENERATED_HEADER}\n{HASH_PREFIX}{doc.content_hash} -->\n{FULL_AGENTS_MD}"
        )

        checks = revert_hand_edits(tmp_path)
        assert len(checks) == 0
