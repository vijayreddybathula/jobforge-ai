"""Structured logging configuration."""

import logging
import sys
import json
from datetime import datetime
from typing import Any, Dict, Optional
import uuid


class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data: Dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add correlation ID if present
        if hasattr(record, "correlation_id"):
            log_data["correlation_id"] = record.correlation_id

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add extra fields
        if hasattr(record, "extra_fields"):
            log_data.update(record.extra_fields)

        return json.dumps(log_data)


def setup_logging(level: str = "INFO") -> None:
    """Setup structured logging."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())

    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper()))
    root_logger.addHandler(handler)

    # Set levels for noisy libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("celery").setLevel(logging.INFO)


def get_logger(name: str) -> logging.Logger:
    """Get logger with name."""
    return logging.getLogger(name)


class CorrelationContext:
    """Context manager for correlation IDs."""

    def __init__(self, correlation_id: Optional[str] = None):
        self.correlation_id = correlation_id or str(uuid.uuid4())
        self.old_correlation_id = None

    def __enter__(self):
        # Store old correlation ID if any
        import contextvars

        try:
            correlation_var = contextvars.ContextVar("correlation_id")
            self.old_correlation_id = correlation_var.get(None)
            correlation_var.set(self.correlation_id)
        except Exception:
            pass
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Restore old correlation ID
        import contextvars

        try:
            correlation_var = contextvars.ContextVar("correlation_id")
            if self.old_correlation_id is not None:
                correlation_var.set(self.old_correlation_id)
            else:
                correlation_var.set(None)
        except Exception:
            pass
