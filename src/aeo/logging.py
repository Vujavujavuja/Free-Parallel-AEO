"""structlog configuration.

Emits human-friendly console logs by default. Secrets are never logged: the
OpenRouter key is stored as a ``SecretStr`` and this module additionally
redacts any value that looks like an API key from event dicts.
"""

from __future__ import annotations

import logging
import re
import sys
from typing import Any

import structlog

_SECRET_RE = re.compile(r"sk-or-[A-Za-z0-9._-]+")
_REDACTED = "***REDACTED***"
_configured = False


def _redact_secrets(
    _logger: Any, _method: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    """structlog processor that scrubs anything resembling an OpenRouter key."""
    for key, value in list(event_dict.items()):
        if isinstance(value, str) and _SECRET_RE.search(value):
            event_dict[key] = _SECRET_RE.sub(_REDACTED, value)
        if key.lower() in {"authorization", "api_key", "openrouter_api_key", "token"}:
            event_dict[key] = _REDACTED
    return event_dict


def configure_logging(level: str = "INFO", *, json_logs: bool = False) -> None:
    """Configure structlog + stdlib logging once per process (idempotent)."""
    global _configured
    if _configured:
        return

    log_level = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=log_level)

    processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        _redact_secrets,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]
    if json_logs:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
    _configured = True


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Return a bound structlog logger."""
    return structlog.get_logger(name)  # type: ignore[no-any-return]
