"""settfex must not touch the host application's logging — issue #146.

Until 0.24.2, importing anything from ``settfex.utils`` destroyed every loguru handler in the
process. ``settfex/utils/logging.py`` ran ``setup_logger(level="ERROR")`` at import, and
``setup_logger`` called ``logger.remove()`` **with no argument**, which removes *all* handlers,
not just settfex's. A host that had configured its own sinks lost them: everything below ERROR
vanished, ERROR vanished from its **files**, and whatever still reached stderr was re-rendered in
settfex's format, because settfex's handler had become the only one in the process.

**These tests run in subprocesses, and they have to.** A module cannot be un-imported, and settfex
is already imported inside the pytest process, so an in-process "configure a sink, then import"
test would import nothing and silently assert nothing. Each test below drives a fresh interpreter,
which is the only way to exercise import-time behaviour honestly. ``tests/test_typing_surface.py``
shells out for the same class of reason.
"""

from __future__ import annotations

import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def run_in_fresh_interpreter(script: str, tmp_path: Path) -> subprocess.CompletedProcess[str]:
    """Execute ``script`` in a new interpreter rooted at the repo, so ``import settfex`` works."""
    path = tmp_path / "scenario.py"
    path.write_text(textwrap.dedent(script), encoding="utf-8")
    return subprocess.run(
        [sys.executable, str(path)],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        check=False,
    )


class TestTheHostKeepsItsSinks:
    """(a) The defect itself: a sink configured before the import must survive it."""

    def test_a_host_file_sink_survives_importing_settfex(self, tmp_path: Path) -> None:
        """Fails on 0.24.1 and earlier: every AFTER-IMPORT line is missing from the file.

        The assertion covers ERROR as well as WARNING deliberately — the old behaviour left one
        stderr handler at ERROR, so it was tempting to assume errors still reached the host. They
        did not: the host's **file** sink was gone, so ERROR was lost there too.
        """
        log = tmp_path / "host_app.log"
        result = run_in_fresh_interpreter(
            f"""
            from loguru import logger
            logger.remove()
            logger.add({str(log)!r}, level="DEBUG")

            logger.warning("BEFORE: host warning")

            from settfex.utils import AsyncDataFetcher            # the import under test
            from settfex.services.sec.financial_report import FinancialReportService
            FinancialReportService()                              # a real public call

            logger.warning("AFTER: host warning")
            logger.info("AFTER: host info")
            logger.error("AFTER: host error")
            logger.remove()                                       # flush the file sink
            """,
            tmp_path,
        )
        assert result.returncode == 0, result.stderr
        text = log.read_text(encoding="utf-8")

        assert "BEFORE: host warning" in text, "the sink was not working before the import"
        for expected in ("AFTER: host warning", "AFTER: host info", "AFTER: host error"):
            assert expected in text, (
                f"{expected!r} is missing: importing settfex destroyed the host's sink. "
                f"settfex must not call logger.remove() without an argument, and must not touch "
                f"handlers at import at all. See issue #146.\n\nLog contained:\n{text}"
            )


class TestSettfexIsSilentUntilAskedFor:
    """(b) Silent by default, and opt-in-able — both halves, or the contract is half-pinned."""

    def test_settfex_logs_nothing_by_default(self, tmp_path: Path) -> None:
        log = tmp_path / "quiet.log"
        result = run_in_fresh_interpreter(
            f"""
            from loguru import logger
            logger.remove()
            logger.add({str(log)!r}, level="DEBUG", format="{{name}} | {{message}}")

            from settfex.services.sec.financial_report import FinancialReportService
            FinancialReportService()                    # logs at INFO inside settfex
            logger.info("host line")
            logger.remove()
            """,
            tmp_path,
        )
        assert result.returncode == 0, result.stderr
        text = log.read_text(encoding="utf-8")

        assert "host line" in text, "the host's own logging must be unaffected"
        assert "settfex." not in text, (
            f"settfex emitted a record without being asked. The package root must call "
            f"logger.disable('settfex').\n\nLog contained:\n{text}"
        )

    def test_enable_makes_settfex_log_through_the_hosts_sinks(self, tmp_path: Path) -> None:
        """The opt-in path that costs the caller nothing: their sinks, their format."""
        log = tmp_path / "enabled.log"
        result = run_in_fresh_interpreter(
            f"""
            from loguru import logger
            logger.remove()
            logger.add({str(log)!r}, level="DEBUG", format="{{name}} | {{message}}")

            from settfex.services.sec.financial_report import FinancialReportService
            logger.enable("settfex")                    # opt in
            FinancialReportService()
            logger.remove()
            """,
            tmp_path,
        )
        assert result.returncode == 0, result.stderr
        text = log.read_text(encoding="utf-8")
        assert "settfex." in text, (
            f"logger.enable('settfex') did not restore settfex's records.\n\nLog:\n{text}"
        )


class TestSetupLoggerOnlyRemovesItsOwn:
    """(c) setup_logger() is idempotent, and never takes a handler it did not add."""

    def test_calling_it_twice_does_not_accumulate_and_keeps_the_host_sink(
        self, tmp_path: Path
    ) -> None:
        """Two properties in one scenario, because they share a failure mode.

        The old implementation could only clean up with a bare ``logger.remove()``, which is
        exactly what made it destructive. Tracking its own handler ids is what lets it be
        idempotent *and* harmless.
        """
        host_log = tmp_path / "host.log"
        result = run_in_fresh_interpreter(
            f"""
            from loguru import logger
            logger.remove()
            host_id = logger.add({str(host_log)!r}, level="DEBUG")

            from settfex.utils.logging import setup_logger

            setup_logger(level="INFO")
            setup_logger(level="INFO")
            setup_logger(level="INFO")

            logger.info("host line after three setup_logger calls")
            logger.remove()
            print("OK")
            """,
            tmp_path,
        )
        assert result.returncode == 0, result.stderr

        text = host_log.read_text(encoding="utf-8")
        assert "host line after three setup_logger calls" in text, (
            f"setup_logger() removed the host's sink. It must remove only the handler ids it "
            f"added itself.\n\nLog contained:\n{text}"
        )

        # Three identical calls must leave one settfex stderr handler, not three: the host's
        # message would otherwise appear three times on stderr.
        assert result.stderr.count("host line after three setup_logger calls") <= 1, (
            f"setup_logger() accumulated handlers across calls; the line was echoed "
            f"{result.stderr.count('host line after three setup_logger calls')} times.\n"
            f"{result.stderr}"
        )

    def test_setup_logger_enables_settfex(self, tmp_path: Path) -> None:
        """Calling it IS the opt-in — otherwise it would configure sinks that receive nothing."""
        log = tmp_path / "viaset.log"
        result = run_in_fresh_interpreter(
            f"""
            from settfex.utils.logging import setup_logger
            from loguru import logger

            setup_logger(level="INFO")
            logger.remove()                              # drop setup_logger's own stderr sink
            logger.add({str(log)!r}, level="DEBUG", format="{{name}} | {{message}}")

            from settfex.services.sec.financial_report import FinancialReportService
            FinancialReportService()
            logger.remove()
            """,
            tmp_path,
        )
        assert result.returncode == 0, result.stderr
        assert "settfex." in log.read_text(encoding="utf-8"), (
            "setup_logger() must call logger.enable('settfex')"
        )


@pytest.mark.parametrize(
    "entry_point",
    [
        "from settfex.utils import AsyncDataFetcher",
        "from settfex.utils.data_fetcher import AsyncDataFetcher",
        "import settfex",
        "from settfex import get_stock_list",
    ],
    ids=["utils", "utils.data_fetcher", "settfex", "settfex.get_stock_list"],
)
def test_no_import_path_destroys_the_host_sink(entry_point: str, tmp_path: Path) -> None:
    """The defect was reachable by several routes, so the guard covers several routes.

    ``settfex/utils/__init__.py`` imports the logging module, and the package root imports the
    utils package, so there was no import of settfex that did not trigger it.
    """
    log = tmp_path / f"host_{abs(hash(entry_point))}.log"
    result = run_in_fresh_interpreter(
        f"""
        from loguru import logger
        logger.remove()
        logger.add({str(log)!r}, level="DEBUG")

        {entry_point}

        logger.warning("survived")
        logger.remove()
        """,
        tmp_path,
    )
    assert result.returncode == 0, result.stderr
    assert "survived" in log.read_text(encoding="utf-8"), (
        f"`{entry_point}` destroyed the host's sink (issue #146)"
    )
