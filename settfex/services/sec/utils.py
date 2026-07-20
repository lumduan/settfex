"""Utilities for the SEC IDISC services: headers, ASP.NET token scraping, an HTML result-table
parser (stdlib only), and small value coercers.

The SEC site is server-rendered ASP.NET HTML with no JSON list endpoint, so listing means
parsing HTML tables. Parsing uses the standard library ``html.parser`` (no new dependency).
"""

from __future__ import annotations

import re
from datetime import date, datetime
from html import unescape
from html.parser import HTMLParser
from typing import Any
from urllib.parse import parse_qs, urljoin, urlparse

from settfex.services.sec.constants import (
    SEC_ASPNET_TOKEN_FIELDS,
    SEC_BASE_URL,
    SEC_REFERER,
)

# ---------------------------------------------------------------------------
# Headers
# ---------------------------------------------------------------------------


def build_sec_headers(referer: str = SEC_REFERER, *, origin: bool = False) -> dict[str, str]:
    """
    Browser-like headers for market.sec.or.th requests (Incapsula-friendly, mirrors SET).

    ``Content-Type`` is intentionally omitted — ``curl_cffi`` sets it automatically for JSON
    vs form bodies. Pass ``origin=True`` for POSTs that want an ``Origin`` header.
    """
    headers = {
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;q=0.9,application/json,*/*;q=0.8"
        ),
        "Accept-Language": "en-US,en;q=0.9,th-TH;q=0.8,th;q=0.7",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "Referer": referer,
        "Sec-Ch-Ua": '"Chromium";v="120", "Not=A?Brand";v="24", "Google Chrome";v="120"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Windows"',
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
    }
    if origin:
        headers["Origin"] = SEC_BASE_URL
    return headers


# ---------------------------------------------------------------------------
# ASP.NET postback token scraping
# ---------------------------------------------------------------------------


def extract_aspnet_tokens(html: str) -> dict[str, str]:
    """
    Scrape the hidden ASP.NET postback tokens (__VIEWSTATE etc.) from a GET page.

    These MUST be echoed back on the search POST — omitting them does not error but silently
    returns a wrong (broader) result set. Returns a dict with every field in
    ``SEC_ASPNET_TOKEN_FIELDS`` (value ``""`` if a field is unexpectedly absent).
    """
    tokens: dict[str, str] = {}
    for field in SEC_ASPNET_TOKEN_FIELDS:
        match = re.search(rf'id="{re.escape(field)}"[^>]*value="([^"]*)"', html)
        tokens[field] = unescape(match.group(1)) if match else ""
    return tokens


# ---------------------------------------------------------------------------
# HTML result-table parsing
# ---------------------------------------------------------------------------


class ReportRow(dict[str, Any]):
    """A parsed result-table row: ``section`` (card heading), ``headers``, ``cells``, ``href``."""


class _ReportTableParser(HTMLParser):
    """Extract (section-heading, column-headers, row-cells, first-href) tuples from result HTML.

    The result panel is a sequence of ``<div class="card-heading">…</div>`` + ``<table>`` pairs;
    each table has a ``<th>`` header row followed by ``<td>`` data rows. We track the current
    heading and, per table, the header list; each data row is emitted with its section + the
    first anchor href found in the row (the download link).
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[ReportRow] = []
        self._section = ""
        self._heading_depth = 0  # >0 while inside a card-heading div (handles nested divs)
        self._heading_buf: list[str] = []
        self._in_table = False
        self._headers: list[str] = []
        self._in_th = False
        self._in_td = False
        self._cell_buf: list[str] = []
        self._row: list[str] = []
        self._row_href: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        adict = {k: (v or "") for k, v in attrs}
        cls = adict.get("class", "")
        if tag == "div":
            if self._heading_depth > 0:
                self._heading_depth += 1
            elif "card-heading" in cls:
                self._heading_depth = 1
                self._heading_buf = []
        elif tag == "table":
            self._in_table = True
            self._headers = []
        elif tag == "tr":
            self._row = []
            self._row_href = None
        elif tag == "th" and self._in_table:
            self._in_th = True
            self._cell_buf = []
        elif tag == "td" and self._in_table:
            self._in_td = True
            self._cell_buf = []
        elif tag == "a" and self._in_td and self._row_href is None:
            href = adict.get("href", "")
            if href:
                self._row_href = href

    def handle_data(self, data: str) -> None:
        if self._heading_depth > 0:
            self._heading_buf.append(data)
        elif self._in_th or self._in_td:
            self._cell_buf.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "div" and self._heading_depth > 0:
            self._heading_depth -= 1
            if self._heading_depth == 0:
                self._section = re.sub(r"\s+", " ", "".join(self._heading_buf)).strip()
        elif tag == "th" and self._in_th:
            self._headers.append(re.sub(r"\s+", " ", "".join(self._cell_buf)).strip())
            self._in_th = False
        elif tag == "td" and self._in_td:
            self._row.append(re.sub(r"\s+", " ", "".join(self._cell_buf)).strip())
            self._in_td = False
        elif tag == "tr":
            # Emit a data row only (header rows have <th>, so self._row stays empty for them).
            if self._row and self._headers:
                self.rows.append(
                    ReportRow(
                        section=self._section,
                        headers=list(self._headers),
                        cells=list(self._row),
                        href=self._row_href,
                    )
                )
            self._row = []
            self._row_href = None
        elif tag == "table":
            self._in_table = False
            self._headers = []


def parse_report_tables(html: str) -> list[ReportRow]:
    """Parse a SEC result page/panel into a flat list of :class:`ReportRow` (one per data row)."""
    parser = _ReportTableParser()
    parser.feed(html)
    return parser.rows


# ---------------------------------------------------------------------------
# Value coercers
# ---------------------------------------------------------------------------


def parse_dmy_date(value: str | None) -> date | None:
    """Parse a dd/MM/yyyy result-cell date; return None for blank/unparseable input."""
    if not value:
        return None
    text = value.strip()
    if not text:
        return None
    try:
        return datetime.strptime(text, "%d/%m/%Y").date()
    except ValueError:
        return None


def parse_int(value: str | None) -> int | None:
    """Parse an integer from a result cell (e.g. a year); None if not an integer."""
    if not value:
        return None
    match = re.search(r"-?\d+", value.replace(",", ""))
    return int(match.group(0)) if match else None


def classify_download_href(href: str | None) -> tuple[str, str | None, str | None]:
    """
    Resolve a row href to (absolute_url, file_id, file_kind).

    - IDISC downloads: ``/public/idisc/Download?FILEID=<path>`` → file_id=<path>, kind from ext.
    - IPOS downloads:  ``/ipos/Common/IPOSGetFile.aspx?id=<id>`` → file_id="ipos:<id>", kind=None.
    Relative hrefs are resolved against the SEC base URL.
    """
    if not href:
        return "", None, None
    absolute = urljoin(SEC_BASE_URL + "/public/idisc/en/FinancialReport/ALL", unescape(href))
    parsed = urlparse(absolute)
    query = parse_qs(parsed.query)
    if "FILEID" in query:
        file_id = query["FILEID"][0]
        ext = file_id.rsplit(".", 1)[-1].lower() if "." in file_id else None
        kind = ext if ext in {"zip", "pdf", "xlsx", "doc", "docx"} else None
        return absolute, file_id, kind
    if parsed.path.lower().endswith("iposgetfile.aspx") and "id" in query:
        return absolute, f"ipos:{query['id'][0]}", None
    # Not a recognized download link (e.g. a "display all results" ViewMore link) — not a doc.
    return "", None, None
