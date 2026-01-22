"""Logging configuration for client and server with rotating file handlers."""

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional


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
