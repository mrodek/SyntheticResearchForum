"""SRF structured logging via structlog — JSON lines, context-bound per coroutine."""

from __future__ import annotations

import logging
import sys
from typing import IO, Any

import structlog
import structlog.contextvars
import structlog.stdlib


def configure_logging(level: str = "INFO", stream: IO[str] | None = None) -> None:
    """Configure structlog for JSON output.

    Call once at application startup. In tests, pass ``stream`` to capture output.
    Clears contextvars on each call to prevent test bleed.
    """
    if stream is None:
        stream = sys.stdout

    structlog.contextvars.clear_contextvars()

    # Configure the stdlib root logger to write to the given stream.
    root = logging.getLogger()
    for handler in root.handlers[:]:
        root.removeHandler(handler)
    sh = logging.StreamHandler(stream)
    sh.setFormatter(logging.Formatter("%(message)s"))
    root.addHandler(sh)
    root.setLevel(getattr(logging, level.upper()))

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", key="timestamp"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=False,
    )


def get_logger(component: str) -> structlog.stdlib.BoundLogger:
    """Return a structlog logger bound with the given component name."""
    return structlog.get_logger(component).bind(component=component)


def bind_context(**kwargs: Any) -> None:
    """Bind key-value pairs into the current async context (contextvars)."""
    structlog.contextvars.bind_contextvars(**kwargs)
