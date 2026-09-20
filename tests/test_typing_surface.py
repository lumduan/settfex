"""The shipped type hints are an interface, so they get a test.

settfex ships ``py.typed``. That makes every annotation a promise to consumers running mypy, and
for an agent reading the package it is a *primary* channel — often the only description of a return
value it ever sees.

`mypy settfex/` cannot catch a broken promise here, and 0.24.0 proved it. When the two SEC
containers became Pydantic models, ``__getitem__`` was annotated ``int | slice -> Item | Container``
and the library's own type check stayed green **because the library never indexes these containers**.
Every consumer, meanwhile, got a ``union-attr`` error on the most ordinary call there is::

    docs[0].year        # Item "SecDocumentList" of "SecDocument | SecDocumentList" has no
                        # attribute "year"
    docs[:5].accounting # Item "SecDocument" of ... has no attribute "accounting"

Reported by a downstream consumer type-checking against the rc, not by our own gates. The fix is
``@overload``; this test is what keeps it.

It works by type-checking a snippet the way a consumer would, with ``typing.assert_type`` so the
assertion is on the **exact inferred type** rather than merely on the absence of errors — a
snippet that only avoided errors would still pass if indexing silently returned ``Any``.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

#: Type-checked as a consumer would, from outside the package. Every line here is an ordinary call.
CONSUMER_SNIPPET = """
from typing import assert_type

from settfex.services.sec.download import DownloadedFile, DownloadResult
from settfex.services.sec.financial_report import SecDocument, SecDocumentList


def indexing_and_slicing(docs: SecDocumentList, files: DownloadResult) -> None:
    # An integer index yields the ITEM -- the call that regressed.
    assert_type(docs[0], SecDocument)
    assert_type(files[0], DownloadedFile)

    # A slice yields the CONTAINER, which is the whole point of the 0.24.0 redesign: the
    # accounting must survive slicing, and the type must say so.
    assert_type(docs[:5], SecDocumentList)
    assert_type(files[:2], DownloadResult)

    # The attribute access each of those enables, which is what consumers actually write.
    year: int | None = docs[0].year
    name: str = files[0].filename
    losses: bool = docs[:5].accounting.has_losses
    complete: bool = files[:2].is_complete
    print(year, name, losses, complete)


def iteration_is_still_typed(docs: SecDocumentList, files: DownloadResult) -> None:
    for document in docs:
        assert_type(document, SecDocument)
    for downloaded in files:
        assert_type(downloaded, DownloadedFile)


def the_fields_are_reachable(docs: SecDocumentList, files: DownloadResult) -> None:
    # `.documents` / `.files` are what the migration notes point people at, so they must type.
    first: SecDocument = docs.documents[0]
    ordered: list[SecDocument] = sorted(docs.documents, key=lambda d: d.year or 0)
    failures: int = len(files.failed)
    print(first, ordered, failures)
"""


@pytest.fixture(scope="module")
def mypy_on_consumer(tmp_path_factory: pytest.TempPathFactory) -> subprocess.CompletedProcess[str]:
    """Run mypy --strict over the snippet once, from the repo root so settfex resolves."""
    if shutil.which("mypy") is None:  # pragma: no cover - mypy is in the dev group
        pytest.skip("mypy is not installed")
    snippet = tmp_path_factory.mktemp("typing_surface") / "consumer.py"
    snippet.write_text(textwrap.dedent(CONSUMER_SNIPPET), encoding="utf-8")
    return subprocess.run(
        [sys.executable, "-m", "mypy", "--strict", "--no-incremental", str(snippet)],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        check=False,
    )


class TestConsumersCanIndexAndSliceTheSecContainers:
    """The exact defect a downstream consumer reported against 0.24.0rc1."""

    def test_the_snippet_type_checks_cleanly(
        self, mypy_on_consumer: subprocess.CompletedProcess[str]
    ) -> None:
        assert mypy_on_consumer.returncode == 0, (
            "A consumer running mypy --strict against the shipped hints gets errors:\n\n"
            f"{mypy_on_consumer.stdout}\n{mypy_on_consumer.stderr}\n"
            "`mypy settfex/` cannot see this -- the library never indexes these containers -- so "
            "this snippet is the only thing standing between a typing regression and the users."
        )

    def test_no_assert_type_mismatch_slipped_through(
        self, mypy_on_consumer: subprocess.CompletedProcess[str]
    ) -> None:
        """Guard the guard: `assert_type` failures are ordinary errors and must not be tolerated.

        Without this, loosening the return annotation to ``Any`` would make every call "valid"
        and the suite would go green on a strictly worse interface.
        """
        assert "Expression is of type" not in mypy_on_consumer.stdout, (
            f"assert_type mismatch -- indexing returns the wrong type:\n{mypy_on_consumer.stdout}"
        )


class TestTheOverloadsExistAtRuntimeToo:
    """A cheap structural check, so a stripped `__getitem__` fails fast without invoking mypy."""

    @pytest.mark.parametrize(
        "module_path",
        [
            "settfex/services/sec/financial_report.py",
            "settfex/services/sec/download.py",
        ],
    )
    def test_getitem_is_overloaded(self, module_path: str) -> None:
        source = (REPO_ROOT / module_path).read_text(encoding="utf-8")
        assert source.count("@overload") >= 2, (
            f"{module_path}: __getitem__ needs an int overload AND a slice overload. Dropping "
            f"them collapses the hint to a union and breaks every consumer's docs[0].attribute."
        )
