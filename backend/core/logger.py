import json
import logging
import os
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler

# ── Constants ──────────────────────────────────────────────────────────────
_SERVICE_NAME = "api-pulse"
_SERVICE_VERSION = "1.0.0"


class JSONFormatter(logging.Formatter):
    """
    Formats log records as structured JSON for production observability.

    Every log line includes:
      - timestamp  : ISO-8601 UTC
      - level      : DEBUG / INFO / WARNING / ERROR / CRITICAL
      - service    : application name (api-pulse)
      - version    : application version
      - module     : Python module name where log was emitted
      - message    : human-readable log message

    Additional context can be passed via the `extra` kwarg using the key
    ``structured_data`` (a plain dict). Its keys are merged into the top-level
    JSON object, making them easily queryable in log aggregators (Datadog,
    Loki, CloudWatch, etc.).

    Example usage::

        logger.info(
            "CSV Upload complete",
            extra={"structured_data": {
                "user_id": 42,
                "upload_id": "f47ac10b-...",
                "inserted_rows": 997,
            }}
        )
    """

    def format(self, record: logging.LogRecord) -> str:
        log_record: dict = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "service": _SERVICE_NAME,
            "version": _SERVICE_VERSION,
            "module": record.module,
            "message": record.getMessage(),
        }

        # Merge any structured payload passed via extra={"structured_data": {...}}
        if hasattr(record, "structured_data") and isinstance(record.structured_data, dict):
            log_record.update(record.structured_data)

        # Attach exception info if present
        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_record)


def get_logger(name: str) -> logging.Logger:
    """
    Returns a named, JSON-structured logger.

    Configuration is driven entirely by environment variables so it works
    identically in local dev, Docker, and cloud deployments:

    ``LOG_LEVEL``
        Minimum log level to emit. One of DEBUG, INFO, WARNING, ERROR,
        CRITICAL. Defaults to ``INFO``.

    ``LOG_FILE``
        Optional absolute or relative path to a log file. When set, a
        ``RotatingFileHandler`` (10 MB max, 5 backups) is added in addition
        to stdout. Unset or empty → stdout only.

    Args:
        name: Logger name, typically the module or router name
              (e.g. ``"upload_router"``, ``"ml_train"``).

    Returns:
        A configured :class:`logging.Logger` instance.
    """
    logger = logging.getLogger(name)

    if logger.handlers:
        # Already configured — avoid adding duplicate handlers
        return logger

    # ── Log level from environment ─────────────────────────────────────────
    raw_level = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, raw_level, logging.INFO)
    logger.setLevel(level)

    formatter = JSONFormatter()

    # ── Stdout handler (always active) ────────────────────────────────────
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    # ── Optional rotating file handler ────────────────────────────────────
    log_file = os.getenv("LOG_FILE", "").strip()
    if log_file:
        try:
            file_handler = RotatingFileHandler(
                log_file,
                maxBytes=10 * 1024 * 1024,  # 10 MB per file
                backupCount=5,
                encoding="utf-8",
            )
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        except OSError as exc:
            # Don't crash the app if the log file path is invalid;
            # fall back to stdout-only and emit a warning there.
            logger.warning(
                "Could not open LOG_FILE — falling back to stdout only",
                extra={"structured_data": {"log_file": log_file, "error": str(exc)}},
            )

    # Prevent double-logging via the root logger
    logger.propagate = False

    return logger
