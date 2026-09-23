"""Logging utilities using loguru.

settfex is **silent by default**. The package root calls ``logger.disable("settfex")`` at import,
so nothing here emits a record until the caller opts in — with :func:`setup_logger`, or with
``logger.enable("settfex")`` to route settfex's records through sinks the caller already has.

⚠️ **Nothing in this module touches loguru handlers at import time.** Until 0.24.2 it did: a
module-level ``setup_logger(level="ERROR")`` call ran ``logger.remove()`` with no argument, which
removes **every** handler in the process — so merely importing settfex deleted the host
application's sinks, file sinks included, and left one stderr handler at ERROR. The host then lost
everything below ERROR, lost ERROR from its files, and saw its surviving output re-rendered in
settfex's format. See issue #146.
"""

import contextlib
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from loguru import FilterDict, FilterFunction, Logger

#: Handler ids added by :func:`setup_logger`, so it can remove **its own** and nothing else.
#: ``logger.add()`` returns an id and the old code discarded it, which is why the only way it
#: could clean up was ``logger.remove()`` -- the blunt call that took the host's sinks with it.
_OWN_HANDLER_IDS: list[int] = []


def setup_logger(
    level: str = "INFO",
    log_file: str | Path | None = None,
    rotation: str = "10 MB",
    retention: str = "1 week",
    format_string: str | None = None,
    colorize: bool = True,
    filter: "str | FilterFunction | FilterDict | None" = None,  # loguru's own argument name
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
        filter: Passed to both sinks as loguru's own ``filter`` argument (a module-name prefix,
            a function taking the record, or a ``{name: level}`` dict). ``None``, the default,
            leaves them unfiltered, exactly as before 0.25.0. ``filter="settfex"`` makes them
            receive settfex's records only, which is what an application that also logs through
            loguru usually wants.

    .. warning::
       **By default the sinks this installs are unfiltered — they receive EVERY record in the
       process, not only settfex's.** If your application already configures loguru, calling this
       without ``filter`` will also print *your* lines to stderr in settfex's format. Pass
       ``filter="settfex"``, or skip this function entirely::

           import settfex                      # import FIRST
           from loguru import logger
           logger.enable("settfex")           # route settfex's records through YOUR sinks

       ⚠️ That ``enable`` must come **after** ``import settfex``. The package root disables
       settfex at import and loguru lets the later call win, so an ``enable()`` issued before
       the import is silently undone — no error, the records simply never arrive.

       The default stays unfiltered on purpose: some callers use this function to configure
       logging for their own script or notebook too, and filtering by default would silence them.

    Calling this repeatedly is safe: it removes the handlers it previously added, and only those.

    Example:
        >>> from settfex.utils.logging import setup_logger
        >>> setup_logger(level="DEBUG", log_file="logs/settfex.log")
        >>> setup_logger(level="INFO", filter="settfex")   # settfex's records only
    """
    # Enable settfex's own records. The package root disables them at import so that a
    # caller who never asks for logs never gets any; calling this function IS the ask.
    logger.enable("settfex")

    # Remove only the handlers THIS function added previously, so calling it twice does not
    # accumulate sinks -- and never the caller's, which is the whole point of #146.
    global _OWN_HANDLER_IDS
    for handler_id in _OWN_HANDLER_IDS:
        # Already gone is fine: the caller may have removed it, or run logger.remove().
        with contextlib.suppress(ValueError):
            logger.remove(handler_id)
    _OWN_HANDLER_IDS = []

    # Default format with timestamp, level, and message
    if format_string is None:
        format_string = (
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
            "<level>{message}</level>"
        )

    # Add console handler (stderr)
    _OWN_HANDLER_IDS.append(
        logger.add(
            sys.stderr,
            format=format_string,
            level=level,
            colorize=colorize,
            filter=filter,
            backtrace=True,
            diagnose=True,
        )
    )

    # Add file handler if log_file is specified
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        _OWN_HANDLER_IDS.append(
            logger.add(
                str(log_path),
                format=format_string,
                level=level,
                rotation=rotation,
                retention=retention,
                compression="zip",
                filter=filter,
                backtrace=True,
                diagnose=True,
            )
        )

        logger.info(f"Logging to file: {log_path}")


def get_logger() -> "Logger":
    """
    Get the configured loguru logger instance.

    Returns:
        The global loguru logger instance.

    .. note::
       This is loguru's process-wide logger, not a settfex-specific one. Records it emits from
       **your** modules are unaffected by settfex being disabled — ``logger.disable("settfex")``
       filters on the *record's* module name, so only settfex's own records are suppressed.

    Example:
        >>> from settfex.utils.logging import get_logger
        >>> log = get_logger()
        >>> log.info("This is a log message")
    """
    return logger
