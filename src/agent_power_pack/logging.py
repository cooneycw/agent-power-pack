"""Structured logging configuration via structlog.

JSON to stdout with bound fields: component, event, duration_ms, error.
See specs/001-foundation/research.md §5.
"""

from __future__ import annotations

import logging
import sys

import structlog


def configure_logging(*, level: int = logging.INFO) -> None:
    """Configure structlog for JSON output to stdout.

    Call once at application startup (e.g. in the CLI entrypoint).
    """
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", key="ts"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )

    # Bridge stdlib logging into structlog so third-party libs also emit JSON.
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=level,
    )


def get_logger(component: str) -> structlog.stdlib.BoundLogger:
    """Return a structlog logger pre-bound with a component name.

    Args:
        component: Identifies the subsystem (e.g. "manifest.loader", "cli").
    """
    return structlog.get_logger(component=component)
