"""Logging configuration for client and server with rotating file handlers."""

import logging
import sys
import time
from contextlib import contextmanager
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Generator, Optional


def setup_logger(
    name: str,
    log_file: Optional[Path] = None,
    level: int = logging.INFO,
    max_bytes: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5,
) -> logging.Logger:
    """
    Set up a logger with both stdout and rotating file handlers.

    Args:
        name: Logger name (e.g., 'client' or 'server').
        log_file: Path to log file. If None, uses ~/.markdown-qa/logs/{name}.log.
        level: Logging level (default: INFO).
        max_bytes: Maximum size of log file before rotation (default: 10MB).
        backup_count: Number of backup files to keep (default: 5).

    Returns:
        Configured logger instance.
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Remove existing handlers to avoid duplicates
    logger.handlers.clear()

    # Create formatter
    formatter = logging.Formatter(
        fmt="[%(asctime)s] p%(process)s {%(pathname)s:%(lineno)d} %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Add stdout handler
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setLevel(level)
    stdout_handler.setFormatter(formatter)
    logger.addHandler(stdout_handler)

    # Add rotating file handler
    if log_file is None:
        log_dir = Path.home() / ".markdown-qa" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / f"{name}.log"
    else:
        log_file.parent.mkdir(parents=True, exist_ok=True)

    file_handler = RotatingFileHandler(
        str(log_file),
        maxBytes=max_bytes,
        backupCount=backup_count,
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Prevent propagation to root logger
    logger.propagate = False

    return logger


# Module-level loggers for client and server
_client_logger: Optional[logging.Logger] = None
_server_logger: Optional[logging.Logger] = None


def get_client_logger() -> logging.Logger:
    """
    Get or create the client logger.

    Returns:
        Client logger instance.
    """
    global _client_logger
    if _client_logger is None:
        _client_logger = setup_logger("client")
    return _client_logger


def get_server_logger() -> logging.Logger:
    """
    Get or create the server logger.

    Returns:
        Server logger instance.
    """
    global _server_logger
    if _server_logger is None:
        _server_logger = setup_logger("server")
    return _server_logger


class LatencyTracker:
    """Tracks latency for multiple operations within a request."""

    def __init__(self) -> None:
        """Initialize latency tracker."""
        self._start_time: Optional[float] = None
        self._timings: dict[str, float] = {}

    def start(self) -> None:
        """Start the overall request timer."""
        self._start_time = time.perf_counter()

    @contextmanager
    def track(self, operation: str) -> Generator[None, None, None]:
        """
        Context manager to track latency of an operation.

        Args:
            operation: Name of the operation being tracked.

        Yields:
            None
        """
        op_start = time.perf_counter()
        try:
            yield
        finally:
            elapsed_ms = (time.perf_counter() - op_start) * 1000
            self._timings[operation] = elapsed_ms

    def get_timing(self, operation: str) -> Optional[float]:
        """
        Get the timing for a specific operation.

        Args:
            operation: Name of the operation.

        Returns:
            Elapsed time in milliseconds, or None if not tracked.
        """
        return self._timings.get(operation)

    def get_total_ms(self) -> float:
        """
        Get total elapsed time since start() was called.

        Returns:
            Total elapsed time in milliseconds.
        """
        if self._start_time is None:
            return 0.0
        return (time.perf_counter() - self._start_time) * 1000

    def format_log(self, prefix: str = "") -> str:
        """
        Format all tracked timings as a structured log string.

        Args:
            prefix: Optional prefix for the log message.

        Returns:
            Formatted log string with all timings.
        """
        parts = [prefix] if prefix else []
        parts.append(f"total_ms={self.get_total_ms():.2f}")
        for op, ms in self._timings.items():
            parts.append(f"{op}_ms={ms:.2f}")
        return " ".join(parts)
