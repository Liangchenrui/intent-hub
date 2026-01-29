"""Custom logging module."""

import logging
import sys
from pathlib import Path
from typing import Optional


def setup_logger(
    name: str = "intent Hub",
    level: int = logging.INFO,
    log_file: Optional[str] = None,
    format_string: Optional[str] = None,
) -> logging.Logger:
    """Create and return a configured logger instance.

    Args:
        name: Logger name.
        level: Log level.
        log_file: Optional log file path; if None, output to console only.
        format_string: Optional format string.

    Returns:
        Configured logger instance.
    """
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger

    logger.setLevel(level)

    if format_string is None:
        format_string = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    formatter = logging.Formatter(format_string, datefmt="%Y-%m-%d %H:%M:%S")

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


def suppress_health_check_logs():
    """Suppress Werkzeug access logs for /health requests."""
    class HealthCheckFilter(logging.Filter):
        def filter(self, record: logging.LogRecord) -> bool:
            try:
                msg = (record.getMessage() or "") if hasattr(record, "getMessage") else str(getattr(record, "msg", ""))
            except Exception:
                return True
            if " /health " in msg or '"/health' in msg:
                return False
            return True

    wlog = logging.getLogger("werkzeug")
    wlog.addFilter(HealthCheckFilter())


logger = setup_logger("intent Hub", logging.INFO)

