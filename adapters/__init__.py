"""Runtime adapter package for agent-power-pack.

Each subpackage implements the RuntimeAdapter protocol for a specific runtime.
"""

from __future__ import annotations


class AdapterNotImplemented(NotImplementedError):
    """Raised by stub adapters that are not yet implemented."""
