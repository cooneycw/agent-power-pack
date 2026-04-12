"""InstallReport dataclass returned by every runtime adapter's install() function.

See specs/001-foundation/research.md §6 and data-model.md for context.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class InstallReport:
    """Result of a single adapter install() call.

    Attributes:
        files_written: Paths of files the adapter created or overwrote.
        files_skipped: Paths the adapter chose not to write (e.g. unchanged).
        validation_errors: Human-readable descriptions of manifests that
            failed adapter-specific validation and were not installed.
    """

    files_written: list[Path] = field(default_factory=list)
    files_skipped: list[Path] = field(default_factory=list)
    validation_errors: list[str] = field(default_factory=list)
    duration_ms: int = 0

    @property
    def ok(self) -> bool:
        """True if no validation errors occurred."""
        return len(self.validation_errors) == 0

    @property
    def total(self) -> int:
        """Total number of files processed (written + skipped)."""
        return len(self.files_written) + len(self.files_skipped)
