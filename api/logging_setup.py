"""Structured (JSON) logging: one JSON object per line, easy to search and parse.

Only fields listed in `LOG_FIELDS` are copied from a record's `extra`, so a
transaction payload can never end up in the logs by accident.
"""
import json
import logging
import sys
from datetime import UTC, datetime

LOGGER_NAME = "api"
LOG_FIELDS = (
    "request_id", "method", "endpoint", "path", "status", "latency_ms",
    "risk_level", "risk_levels", "batch_size", "error_code", "error_fields",
    "model_version", "model_path", "rows", "error_type", "storage_error_code",
    "demo_run_id", "user_id", "state", "sent", "failed",
)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        entry.update({f: getattr(record, f) for f in LOG_FIELDS if hasattr(record, f)})
        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)  # server-side only
        return json.dumps(entry, default=str)


def configure_logging(level: str) -> logging.Logger:
    """Send the `api` logger's records to stderr as JSON (safe to call repeatedly)."""
    logger = logging.getLogger(LOGGER_NAME)
    logger.handlers = [h for h in logger.handlers if not getattr(h, "_api_json", False)]
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(JsonFormatter())
    handler._api_json = True
    logger.addHandler(handler)
    logger.setLevel(level)
    logger.propagate = False
    return logger
