#!/usr/bin/env python3
"""Derive the committed SEC listing fixtures from captured bodies (#123 / #127 / #131 / #133 / 0.22.2).

Run from the repo root, with the evidence bundles extracted somewhere gitignored. Any number of
bundle roots may be given; each source is resolved against whichever one carries it::

    uv run python tests/services/sec/derive_th_fixtures.py \\
        tmp/issue-123-bundle tmp/issue-127-bundle \\
        tmp/issue-batch-r4/extracted/0004-evidence tmp/issue-fs-r561

What this does, and what it deliberately does not do:

* It reads the **original bytes** and verifies every source sha256 against the bundle's
  ``MANIFEST.md`` before touching anything. A mismatch aborts.
* It slices out the result panel ``<div id="ctl00_CPH_pnlControl">…</div>`` **verbatim** — a byte
  range of the original, not a re-render. Nothing is re-encoded, reformatted, entity-escaped or
  Unicode-normalized, so the Thai text in the fixtures is the text the server sent.
* It drops the surrounding chrome (the ASP.NET ``__VIEWSTATE`` blob, scripts, navigation), which
  no parse test reads. The section headings, the record-count markers, the header rows and the
  table structure are inside the slice and survive untouched.
* The captured bodies carry **no charset declaration** — the site sends it in the ``Content-Type``
  header, and the capture harness recorded bodies only. None is invented here; the fixtures are
  UTF-8 and ``load_fixture`` decodes them explicitly as UTF-8, which is what ``AsyncDataFetcher``
  does with the live response.

Rerunning must produce a zero git diff: the slice is a pure function of the source bytes.
"""

from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path

# (source file stem, derived name). Two issuer-pairs, chosen for what they cover rather than size:
#   PTT H1-2025    - every section populated, including Key Financial Ratio and MD&A data rows.
#   MOTHER H1-2025 - the Key Financial Ratio section is present with its heading and header row
#                    but NO data rows, in both languages. That is a genuine absence of filings,
#                    and it is the case that must return [] without raising.
#   PTT 56-1 / 56-2 - the 56-x sections, which carry the `Receive Date` column the FS sections do
#                     not have. Thai `วันที่ได้รับข้อมูล` was unmapped until #127 P4, so a Thai
#                     annual report lost its only filing timestamp. NOTE the Thai and English 56-1
#                     captures are from DIFFERENT windows (3 vs 6 records), so parity must be
#                     asserted per (form, year), never by comparing counts.
#   G5 / G2       - NOT listing pages: a real HTTP 505 error body and a capital.sec.or.th
#                   indirection page. Both are tiny and are copied VERBATIM (there is no result
#                   panel to slice). They are what the #131 transport guards must reject, and the
#                   #133 download path must resolve.
SELECTED = [
    ("E3_th_PTT_FS_20250101-20250630", "th_ptt_fs_h1_2025.html", "#123", "panel"),
    ("E4_en_PTT_FS_20250101-20250630", "en_ptt_fs_h1_2025.html", "#123", "panel"),
    ("E9_th_MOTHER_FS_20250101-20250630", "th_mother_fs_h1_2025.html", "#123", "panel"),
    ("E10_en_MOTHER_FS_20250101-20250630", "en_mother_fs_h1_2025.html", "#123", "panel"),
    ("F1_th_PTT_56-1", "th_ptt_56_1.html", "#127", "panel"),
    ("F2_en_PTT_56-1", "en_ptt_56_1.html", "#127", "panel"),
    ("F5_th_PTT_56-2", "th_ptt_56_2.html", "#127", "panel"),
    ("F3_en_PTT_56-2", "en_ptt_56_2.html", "#127", "panel"),
    ("G5_idisc_505_error_page", "idisc_505_error_page.html", "#131", "verbatim"),
    ("G2_capital_indirection_en_2013_p12", "capital_indirection_en.html", "#133", "verbatim"),
    # The "display all results" pages for the two slugs that were unmapped until 0.22.2. H1 is the
    # page whose section reports 12 and serves 12. H2 is ENGLISH on purpose: it is the evidence
    # that the 56-2 half of this gap was never Thai-only.
    ("H1_th_CPALL_viewmore_fs-r561", "th_cpall_viewmore_56_1.html", "0.22.2", "panel"),
    ("H2_en_PTT_viewmore_fs-r562", "en_ptt_viewmore_56_2.html", "0.22.2", "panel"),
]

PANEL_START = '<div id="ctl00_CPH_pnlControl"'
DEST = Path(__file__).parent / "fixtures_sec"


def manifest_hashes(bundles: list[Path]) -> dict[str, tuple[Path, str]]:
    """Map ``<name>.html`` -> (source path, sha256), merged across every bundle given.

    Each bundle's ``MANIFEST.md`` is the capture harness's own record; a source is only ever read
    from the bundle that vouches for its hash.
    """
    found: dict[str, tuple[Path, str]] = {}
    for bundle in bundles:
        text = (bundle / "MANIFEST.md").read_text(encoding="utf-8")
        for name, digest in re.findall(r"`fixtures/([^`]+)`.*?`([0-9a-f]{64})`", text):
            found.setdefault(name, (bundle / "fixtures" / name, digest))
    return found


def extract_panel(html: str, source: str) -> str:
    """Return the result-panel element verbatim, by walking div depth from its opening tag."""
    start = html.find(PANEL_START)
    if start < 0:
        raise SystemExit(f"{source}: no {PANEL_START!r} found")
    depth = 0
    for match in re.finditer(r"<div\b|</div>", html[start:]):
        depth += 1 if match.group(0) == "<div" else -1
        if depth == 0:
            return html[start : start + match.end()]
    raise SystemExit(f"{source}: unbalanced <div> after the result panel")


def main(argv: list[str]) -> int:
    given = argv[1:] or ["tmp/issue-123-bundle", "tmp/issue-127-bundle"]
    bundles = [Path(b) for b in given]
    for bundle in bundles:
        if not (bundle / "MANIFEST.md").exists():
            print(f"no MANIFEST.md under {bundle}", file=sys.stderr)
            return 2

    expected = manifest_hashes(bundles)
    DEST.mkdir(exist_ok=True)
    rows: list[tuple[str, str, str, str, int, str]] = []

    for stem, derived_name, issue, mode in SELECTED:
        source_name = f"{stem}.html"
        if source_name not in expected:
            print(f"{source_name} is in no bundle's MANIFEST.md", file=sys.stderr)
            return 1
        source_path, manifest_hash = expected[source_name]
        raw = source_path.read_bytes()
        actual = hashlib.sha256(raw).hexdigest()
        if manifest_hash != actual:
            print(
                f"SHA256 MISMATCH for {source_name}\n"
                f"  manifest {manifest_hash}\n  actual   {actual}",
                file=sys.stderr,
            )
            return 1

        if mode == "verbatim":
            # Not a listing page, so there is no panel to slice — the whole body IS the evidence.
            body = raw
        else:
            body = extract_panel(raw.decode("utf-8"), source_name).encode("utf-8")
        out = DEST / derived_name
        out.write_bytes(body)
        rows.append(
            (
                source_name,
                actual,
                derived_name,
                hashlib.sha256(out.read_bytes()).hexdigest(),
                len(body),
                issue,
            )
        )
        print(f"{source_name} -> {derived_name} ({len(body):,} bytes, {mode})")

    readme = [
        "# SEC listing fixtures — provenance\n",
        "Derived from the response bodies captured for issues #123, #127, #131, #133 and the",
        "0.22.2 slug fix by",
        "`tests/services/sec/derive_th_fixtures.py`, which verifies every source sha256 against the",
        "bundle's `MANIFEST.md` and then either slices the result panel out of the original bytes",
        "or copies the whole body, verbatim in both cases.",
        "Nothing here was re-encoded, reformatted or Unicode-normalized, so the Thai text is exactly",
        "what the server sent.\n",
        "The captured bodies carry **no charset declaration** (the site sends it in the",
        "`Content-Type` header, which the capture recorded no headers for). None was invented: these",
        "files are UTF-8 and the tests decode them explicitly as UTF-8, which is what",
        "`AsyncDataFetcher` does with the live response.\n",
        "Regenerate with:\n",
        "```bash",
        "uv run python tests/services/sec/derive_th_fixtures.py \\",
        "    tmp/issue-123-bundle tmp/issue-127-bundle",
        "```\n",
        "| Issue | Source (bundle) | Source sha256 | Derived | Derived sha256 | Bytes |",
        "|---|---|---|---|---|---|",
    ]
    for src, src_hash, dst, dst_hash, size, issue in rows:
        readme.append(f"| {issue} | `{src}` | `{src_hash}` | `{dst}` | `{dst_hash}` | {size:,} |")
    readme.append("")
    (DEST / "README.md").write_text("\n".join(readme), encoding="utf-8")
    print(f"wrote {DEST / 'README.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
