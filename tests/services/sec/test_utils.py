"""Tests for SEC utils: HTML parser, token scraping, href classification, value coercers."""

from datetime import date

from settfex.services.sec.utils import (
    build_sec_headers,
    classify_download_href,
    extract_aspnet_tokens,
    parse_dmy_date,
    parse_int,
    parse_report_tables,
)
from tests.services.sec.fixtures import (
    FORM_56_1_HTML,
    FS_SEARCH_HTML,
    REPORT_PAGE_HTML,
)


class TestExtractAspnetTokens:
    def test_extracts_all_three_tokens(self) -> None:
        tokens = extract_aspnet_tokens(REPORT_PAGE_HTML)
        assert tokens["__VIEWSTATE"] == "STATE123=="
        assert tokens["__VIEWSTATEGENERATOR"] == "688223AE"
        assert tokens["__EVENTVALIDATION"] == "EVAL456=="

    def test_missing_tokens_yield_empty_strings(self) -> None:
        tokens = extract_aspnet_tokens("<html>no tokens</html>")
        assert tokens["__VIEWSTATE"] == ""
        assert set(tokens) == {"__VIEWSTATE", "__VIEWSTATEGENERATOR", "__EVENTVALIDATION"}


class TestParseReportTables:
    def test_parses_all_sections_and_rows(self) -> None:
        rows = parse_report_tables(FS_SEARCH_HTML)
        sections = {r["section"] for r in rows}
        assert any("Finanacial Statements" in s for s in sections)
        assert any("Key Financial Ratio" in s for s in sections)
        assert any("Discussion and Analysis" in s for s in sections)

    def test_row_carries_headers_cells_and_href(self) -> None:
        rows = parse_report_tables(FS_SEARCH_HTML)
        fs_rows = [r for r in rows if "Finanacial Statements" in r["section"] and r.get("href")]
        assert fs_rows, "expected at least one financial-statement data row with an href"
        row = fs_rows[0]
        assert "Name" in row["headers"] and "As Of" in row["headers"]
        assert row["cells"][0] == "CP ALL PUBLIC COMPANY LIMITED"
        assert "Download?FILEID=" in row["href"]

    def test_header_row_not_emitted_as_data(self) -> None:
        # The "Data not found" placeholder row has no href and a single colspan cell.
        rows = parse_report_tables(FS_SEARCH_HTML)
        revised = [r for r in rows if "need to be revised" in r["section"]]
        assert all(r.get("href") is None for r in revised)

    def test_mda_row_has_date_time_heading_columns(self) -> None:
        rows = parse_report_tables(FS_SEARCH_HTML)
        mda = [r for r in rows if "Discussion and Analysis" in r["section"] and r.get("href")]
        assert mda and mda[0]["headers"] == ["Date", "Time", "Heading", "Link"]
        assert mda[0]["href"].endswith(".pdf")

    def test_form_56_1_rows(self) -> None:
        rows = parse_report_tables(FORM_56_1_HTML)
        data = [r for r in rows if r.get("href")]
        assert len(data) == 2
        assert data[0]["headers"] == ["Name", "Year", "Receive Date", "Details"]


class TestClassifyDownloadHref:
    def test_idisc_zip(self) -> None:
        url, fid, kind = classify_download_href(
            "https://market.sec.or.th/public/idisc/Download?FILEID=dat/news/x.zip"
        )
        assert fid == "dat/news/x.zip"
        assert kind == "zip"

    def test_idisc_pdf(self) -> None:
        _, fid, kind = classify_download_href(
            "https://market.sec.or.th/public/idisc/Download?FILEID=dat/news/x.pdf"
        )
        assert kind == "pdf"

    def test_ipos_href(self) -> None:
        url, fid, kind = classify_download_href(
            "https://market.sec.or.th/ipos/Common/IPOSGetFile.aspx?id=726416&sq=0&v=10"
        )
        assert fid == "ipos:726416"
        assert kind is None

    def test_amp_encoded_href_resolves(self) -> None:
        url, fid, _ = classify_download_href(
            "https://market.sec.or.th/ipos/Common/IPOSGetFile.aspx?id=1&amp;sq=0"
        )
        assert fid == "ipos:1"

    def test_empty_href(self) -> None:
        assert classify_download_href(None) == ("", None, None)


class TestValueCoercers:
    def test_parse_dmy_date(self) -> None:
        assert parse_dmy_date("31/03/2026") == date(2026, 3, 31)
        assert parse_dmy_date("") is None
        assert parse_dmy_date("2026-03-31") is None  # ISO not accepted
        assert parse_dmy_date(None) is None

    def test_parse_int(self) -> None:
        assert parse_int("2025") == 2025
        assert parse_int("1,234") == 1234
        assert parse_int("Year") is None
        assert parse_int(None) is None


class TestBuildSecHeaders:
    def test_defaults_and_origin(self) -> None:
        base = build_sec_headers()
        assert "Referer" in base and "Origin" not in base
        with_origin = build_sec_headers(origin=True)
        assert with_origin["Origin"] == "https://market.sec.or.th"
