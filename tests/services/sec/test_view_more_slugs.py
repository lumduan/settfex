"""The 56-1 / 56-2 "display all results" slugs, unmapped until 0.22.2.

`_CATEGORY_FOR_VIEWMORE_SLUG` covered `fs-norm` / `fs-kf` / `fs-mda` — the three sections a single
`FS` search returns — and nothing else. A 56-1 or 56-2 section over the site's ~10-row inline cap
therefore truncated **even with `follow_view_more=True`**, because the link to its complete list
carried a slug the map did not recognise.

0.22.0's own notes predicted this and said the shortfall WARNING would be what surfaced it. It was,
from the other side of the API: a consumer reading `completeness()` saw 10 of 12 on a Thai 56-1.

The scale, live-probed 2026-09-20 over a 2000–2026 window:

    CPALL  56-1  th   served 11 of 23
    PTT    56-1  th   served 11 of 25
    PTT    56-2  th   served 10 of 15
    PTT    56-2  en   served 10 of 15     <- not a Thai-only gap

Both fixtures here are real captured pages (see ``fixtures_sec/README.md``), and the 56-2 one is
**English on purpose**: it is the evidence for that last line.

Note the `fs-` prefix is the site's own and is not a category hint — `fs-r561` is served by the
56-1 search, not by the FS one. A mapping keyed on the prefix would be wrong.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest

from settfex.services.sec.constants import SEC_VIEWMORE_SLUGS
from settfex.services.sec.financial_report import (
    _CATEGORY_FOR_VIEWMORE_SLUG,
    DocumentCategory,
    FinancialReportService,
)
from settfex.services.sec.utils import parse_report_tables, split_section_count

from .fixtures import REPORT_PAGE_HTML, load_fixture
from .test_financial_report import _make_fetcher, _resp

# A 56-1 search result truncated to one row, with the link to its complete list. Same shape as the
# existing FS_TRUNCATED_HTML constant, which models the equivalent `fs-norm` case.
FORM_56_1_TRUNCATED_HTML = """
<div id="ctl00_CPH_pnlControl">
  <div class="card card-table"><div class="card-heading">56-1 : Annual Registration Statements ( 12 record(s) found)</div>
    <table id="g561"><tbody>
      <tr><th>Name</th><th>Year</th><th>Receive Date</th><th>Details</th></tr>
      <tr><td>CP ALL PUBLIC COMPANY LIMITED</td><td>2025</td><td>26/03/2026</td>
          <td><a href="https://market.sec.or.th/public/idisc/Download?FILEID=dat/f56/inline.zip"><img></a></td></tr>
      <tr><td colspan="4"><a href="/public/idisc/th/ViewMore/fs-r561?UniqueIdReference=0000003875&amp;DateFrom=20150101&amp;DateTo=20261231">Click here to display all results</a></td></tr>
    </tbody></table>
  </div>
</div>
"""


class TestTheSlugMap:
    """Both surfaces state the same fact, and only one of them has a caller."""

    @pytest.mark.parametrize(
        ("slug", "category"),
        [
            ("fs-norm", DocumentCategory.FINANCIAL_STATEMENT),
            ("fs-kf", DocumentCategory.KEY_FINANCIAL_RATIO),
            ("fs-mda", DocumentCategory.MDA),
            ("fs-r561", DocumentCategory.FORM_56_1),
            ("fs-r562", DocumentCategory.FORM_56_2),
        ],
    )
    def test_every_live_slug_is_mapped(self, slug: str, category: DocumentCategory) -> None:
        assert _CATEGORY_FOR_VIEWMORE_SLUG[slug] is category

    def test_every_category_can_be_completed(self) -> None:
        """A category with no slug is one that silently truncates — there must be none left."""
        assert set(_CATEGORY_FOR_VIEWMORE_SLUG.values()) == set(DocumentCategory)

    def test_the_public_constant_agrees(self) -> None:
        """`SEC_VIEWMORE_SLUGS` has no caller, so nothing else would notice it going stale."""
        assert {c.value: s for s, c in _CATEGORY_FOR_VIEWMORE_SLUG.items()} == SEC_VIEWMORE_SLUGS


class TestTheCapturedPages:
    """What the site actually serves behind those two links."""

    @pytest.mark.parametrize(
        ("name", "expected"),
        [("th_cpall_viewmore_56_1.html", 12), ("en_ptt_viewmore_56_2.html", 15)],
    )
    def test_the_page_serves_exactly_what_its_section_reports(
        self, name: str, expected: int
    ) -> None:
        """The premise of following the link at all: it holds the COMPLETE list."""
        rows = parse_report_tables(load_fixture(name))
        counts = {split_section_count(str(r["section"]))[1] for r in rows}
        assert counts == {expected}
        assert len(rows) == expected


class TestItIsFollowedEndToEnd:
    @staticmethod
    async def _list(post_body: str, view_more_body: str, **kwargs: Any) -> Any:
        async def router(url, headers=None, *, method="GET", json_body=None, data=None, **kw):
            if "ViewMore" in url:
                return _resp(view_more_body)
            return _resp(post_body if method == "POST" else REPORT_PAGE_HTML)

        with patch("settfex.services.sec.financial_report.AsyncDataFetcher") as cls:
            _make_fetcher(cls, router)
            return await FinancialReportService().fetch_documents("uid", **kwargs)

    @pytest.mark.asyncio
    async def test_a_truncated_56_1_is_completed(self) -> None:
        """The whole point: 1 inline row becomes the 12 the section reports."""
        docs = await self._list(
            FORM_56_1_TRUNCATED_HTML,
            load_fixture("th_cpall_viewmore_56_1.html"),
            types="form_56_1",
            lang="th",
            follow_view_more=True,
        )
        assert len(docs) == 12
        assert docs.completeness() == {"form_56_1": (12, 12)}
        assert not docs.accounting.has_losses
        assert docs.accounting.is_balanced

    @pytest.mark.asyncio
    async def test_without_following_it_still_truncates(self) -> None:
        """`follow_view_more=False` is unchanged — the shortfall is expected and reported."""
        docs = await self._list(
            FORM_56_1_TRUNCATED_HTML,
            load_fixture("th_cpall_viewmore_56_1.html"),
            types="form_56_1",
            lang="th",
            follow_view_more=False,
        )
        assert len(docs) == 1
        assert docs.completeness() == {"form_56_1": (1, 12)}

    @pytest.mark.asyncio
    async def test_the_accounting_replaces_rather_than_doubles(self) -> None:
        """The ViewMore rows REPLACE the inline one; counting both would break the identity."""
        docs = await self._list(
            FORM_56_1_TRUNCATED_HTML,
            load_fixture("th_cpall_viewmore_56_1.html"),
            types="form_56_1",
            lang="th",
            follow_view_more=True,
        )
        tally = docs.accounting.by_category["form_56_1"]
        assert tally.rows == 12
        assert tally.documents == 12
        assert tally.navigation == 0, "the inline page's nav row is superseded with its rows"

    @pytest.mark.asyncio
    async def test_a_category_nobody_asked_for_is_not_followed(self) -> None:
        """Unchanged behaviour, re-pinned now that two more slugs can match."""
        docs = await self._list(
            FORM_56_1_TRUNCATED_HTML,
            load_fixture("th_cpall_viewmore_56_1.html"),
            types="form_56_2",
            lang="th",
            follow_view_more=True,
        )
        assert list(docs) == []
