"""Manifest validator enforcing Constitution Principle I and vendored-skill attribution.

Validation is offline-safe — no network calls.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from agent_power_pack.manifest.schema import (
    CANONICAL_RUNTIMES,
    SkillManifest,
)


@dataclass
class ValidationError:
    """A single validation failure."""

    manifest_name: str
    rule: str
    message: str


@dataclass
class ValidationResult:
    """Aggregate result of validating one or more manifests."""

    errors: list[ValidationError] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return len(self.errors) == 0

    def add(self, manifest_name: str, rule: str, message: str) -> None:
        self.errors.append(ValidationError(manifest_name, rule, message))


def validate_manifest(
    manifest: SkillManifest,
    *,
    vendor_dir: Optional[Path] = None,
) -> ValidationResult:
    """Validate a single SkillManifest.

    Checks:
      1. Principle I — runtimes must equal the full canonical set.
      2. Vendored attribution — if vendor_dir is provided and the manifest
         has attribution, cross-check commit_sha against vendor/skills/<name>/VERSION.

    Pydantic already enforces name format, family membership, and MCP server names
    at parse time, so those are not re-checked here.

    Args:
        manifest: The manifest to validate.
        vendor_dir: Path to the vendor/skills/ directory (for SHA cross-check).

    Returns:
        A ValidationResult with any errors found.
    """
    result = ValidationResult()

    # --- Principle I: full runtime coverage ---
    declared = frozenset(manifest.runtimes)
    if declared != CANONICAL_RUNTIMES:
        missing = CANONICAL_RUNTIMES - declared
        extra = declared - CANONICAL_RUNTIMES
        parts: list[str] = []
        if missing:
            parts.append(f"missing {sorted(r.value for r in missing)}")
        if extra:
            parts.append(f"unexpected {sorted(r.value for r in extra)}")
        result.add(
            manifest.name,
            "principle_i.full_runtime_coverage",
            f"runtimes must equal the canonical set; {'; '.join(parts)}",
        )

    # Check for duplicates
    if len(manifest.runtimes) != len(set(manifest.runtimes)):
        result.add(
            manifest.name,
            "principle_i.no_duplicate_runtimes",
            "runtimes list contains duplicates",
        )

    # --- Vendored attribution cross-check ---
    if manifest.attribution is not None and vendor_dir is not None:
        version_file = vendor_dir / manifest.name / "VERSION"
        if version_file.exists():
            pinned_sha = version_file.read_text().strip()
            if manifest.attribution.commit_sha != pinned_sha:
                result.add(
                    manifest.name,
                    "vendored.sha_mismatch",
                    f"attribution.commit_sha ({manifest.attribution.commit_sha}) "
                    f"does not match vendor/skills/{manifest.name}/VERSION ({pinned_sha})",
                )
        else:
            result.add(
                manifest.name,
                "vendored.version_file_missing",
                f"vendor/skills/{manifest.name}/VERSION not found",
            )

    return result


def validate_all(
    manifests: list[SkillManifest],
    *,
    vendor_dir: Optional[Path] = None,
) -> ValidationResult:
    """Validate a list of manifests, aggregating all errors.

    Args:
        manifests: Manifests to validate.
        vendor_dir: Path to vendor/skills/ for SHA cross-checks.

    Returns:
        An aggregated ValidationResult.
    """
    result = ValidationResult()
    for manifest in manifests:
        single = validate_manifest(manifest, vendor_dir=vendor_dir)
        result.errors.extend(single.errors)
    return result
