"""JSON-line structured logging -> logs/events.log.

Distinct from the SQLite telemetry store: this is the grep-able audit/event
trail (one JSON object per line), the SQLite table is the aggregation store.

See plan section "Telemetry".
"""
from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict

from . import config

_LOGGER_NAME = "revops_copilot"
_configured = False


class JsonLineFormatter(logging.Formatter):
    """Render each record as a single-line JSON object."""

    def format(self, record: logging.LogRecord) -> str:
        payload: Dict[str, Any] = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created)),
            "level": record.levelname,
            "event": record.getMessage(),
        }
        extra = getattr(record, "extra_fields", None)
        if isinstance(extra, dict):
            for key, value in extra.items():
                if key not in payload:
                    payload[key] = value
        return json.dumps(payload, default=str)


def get_logger() -> logging.Logger:
    """Return the shared, lazily-configured JSON-line logger."""
    global _configured
    logger = logging.getLogger(_LOGGER_NAME)
    if _configured:
        return logger

    logger.setLevel(logging.INFO)
    logger.propagate = False

    formatter = JsonLineFormatter()

    # Console handler (helpful during dev / headless runs).
    stream = logging.StreamHandler()
    stream.setFormatter(formatter)
    logger.addHandler(stream)

    # File handler -> logs/events.log. Never let a filesystem issue crash the app.
    try:
        config.LOGS_DIR.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(config.EVENTS_LOG_PATH, encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except Exception:  # noqa: BLE001 - logging must never break the workflow
        pass

    _configured = True
    return logger


def log_event(event: str, level: int = logging.INFO, **fields: Any) -> None:
    """Emit a structured event line with arbitrary key/value fields."""
    logger = get_logger()
    logger.log(level, event, extra={"extra_fields": fields})
