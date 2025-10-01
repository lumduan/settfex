"""Logging utilities using loguru."""

import sys
from pathlib import Path
from typing import Optional, Union

from loguru import logger


def setup_logger(
    level: str = "INFO",
    log_file: Optional[Union[str, Path]] = None,
    rotation: str = "10 MB",
    retention: str = "1 week",
    format_string: Optional[str] = None,
    colorize: bool = True,
) -> None:
    """
    Configure loguru logger for the settfex library.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional path to log file. If None, only logs to stderr
        rotation: When to rotate log files (e.g., "10 MB", "1 day")
        retention: How long to keep old log files (e.g., "1 week", "30 days")
        format_string: Custom format string. If None, uses default format
        colorize: Whether to colorize console output

    Example:
        >>> from settfex.utils.logging import setup_logger
        >>> setup_logger(level="DEBUG", log_file="logs/settfex.log")
    """
    # Remove default handler
    logger.remove()

    # Default format with timestamp, level, and message
    if format_string is None:
        format_string = (
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
            "<level>{message}</level>"
        )

    # Add console handler (stderr)
    logger.add(
        sys.stderr,
        format=format_string,
        level=level,
        colorize=colorize,
        backtrace=True,
        diagnose=True,
    )

    # Add file handler if log_file is specified
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        logger.add(
            str(log_path),
            format=format_string,
            level=level,
            rotation=rotation,
            retention=retention,
            compression="zip",
            backtrace=True,
            diagnose=True,
        )

        logger.info(f"Logging to file: {log_path}")


def get_logger() -> "logger":
    """
    Get the configured loguru logger instance.

    Returns:
        Loguru logger instance

    Example:
        >>> from settfex.utils.logging import get_logger
        >>> log = get_logger()
        >>> log.info("This is a log message")
    """
    return logger


# Initialize with default configuration
# Users can override by calling setup_logger() in their code
setup_logger(level="INFO", colorize=True)
