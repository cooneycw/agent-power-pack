"""Repo check: verify referenced Make targets, Docker services, CI files exist (T035)."""

from __future__ import annotations

import re
from pathlib import Path

from agent_power_pack.linter.document import AgentsMdDocument
from agent_power_pack.linter.result import LintCheck

_MAKEFILE_TARGET_RE = re.compile(r"^([\w-]+)\s*:", re.MULTILINE)


def _parse_makefile_targets(makefile_path: Path) -> set[str]:
    """Extract target names from a Makefile."""
    text = makefile_path.read_text()
    return set(_MAKEFILE_TARGET_RE.findall(text))


def _parse_compose_services(repo_root: Path) -> set[str] | None:
    """Extract service names from compose.yaml / docker-compose.yml."""
    for name in ("compose.yaml", "compose.yml", "docker-compose.yaml", "docker-compose.yml"):
        candidate = repo_root / name
        if candidate.exists():
            from ruamel.yaml import YAML

            yaml = YAML()
            data = yaml.load(candidate)
            if data and "services" in data:
                return set(data["services"].keys())
    return None


def check_repo(doc: AgentsMdDocument, repo_root: Path) -> list[LintCheck]:
    """Verify referenced artifacts exist in the repo."""
    checks: list[LintCheck] = []

    # Make targets
    makefile = repo_root / "Makefile"
    if makefile.exists():
        actual_targets = _parse_makefile_targets(makefile)
        for target in sorted(doc.referenced_make_targets):
            found = target in actual_targets
            checks.append(
                LintCheck(
                    rule_id="repo.make_target_exists",
                    status="pass" if found else "fail",
                    message=f"Make target '{target}' {'exists' if found else 'not found'} in Makefile",
                    subject=target,
                )
            )
    else:
        for target in sorted(doc.referenced_make_targets):
            checks.append(
                LintCheck(
                    rule_id="repo.make_target_exists",
                    status="warn",
                    message=f"No Makefile found; cannot verify target '{target}'",
                    subject=target,
                )
            )

    # Docker services
    services = _parse_compose_services(repo_root)
    if services is not None:
        for svc in sorted(doc.referenced_docker_services):
            found = svc in services
            checks.append(
                LintCheck(
                    rule_id="repo.docker_service_exists",
                    status="pass" if found else "fail",
                    message=f"Docker service '{svc}' {'exists' if found else 'not found'} in compose file",
                    subject=svc,
                )
            )
    # If no compose file, skip docker checks silently

    # CI files
    for ci_file in sorted(doc.referenced_ci_files):
        exists = (repo_root / ci_file).exists()
        checks.append(
            LintCheck(
                rule_id="repo.ci_file_exists",
                status="pass" if exists else "fail",
                message=f"CI file '{ci_file}' {'exists' if exists else 'not found'} on disk",
                subject=ci_file,
            )
        )

    return checks
