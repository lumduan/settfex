#!/usr/bin/env python3
"""Derive the committed SEC listing fixtures from the captured response bodies of issue #123.

Run from the repo root, with the evidence bundle extracted somewhere gitignored::

    uv run python tests/services/sec/derive_th_fixtures.py tmp/issue-123-bundle

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
SELECTED = [
    ("E3_th_PTT_FS_20250101-20250630", "th_ptt_fs_h1_2025.html"),
    ("E4_en_PTT_FS_20250101-20250630", "en_ptt_fs_h1_2025.html"),
    ("E9_th_MOTHER_FS_20250101-20250630", "th_mother_fs_h1_2025.html"),
    ("E10_en_MOTHER_FS_20250101-20250630", "en_mother_fs_h1_2025.html"),
]

PANEL_START = '<div id="ctl00_CPH_pnlControl"'
DEST = Path(__file__).parent / "fixtures_sec"


def manifest_hashes(bundle: Path) -> dict[str, str]:
    """Map ``fixtures/<name>.html`` -> sha256, as recorded by the capture harness."""
    text = (bundle / "MANIFEST.md").read_text(encoding="utf-8")
    return dict(re.findall(r"`fixtures/([^`]+)`.*?`([0-9a-f]{64})`", text))


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
    bundle = Path(argv[1] if len(argv) > 1 else "tmp/issue-123-bundle")
    if not (bundle / "MANIFEST.md").exists():
        print(f"no MANIFEST.md under {bundle}", file=sys.stderr)
        return 2

    expected = manifest_hashes(bundle)
    DEST.mkdir(exist_ok=True)
    rows: list[tuple[str, str, str, str, int]] = []

    for stem, derived_name in SELECTED:
        source_name = f"{stem}.html"
        source_path = bundle / "fixtures" / source_name
        raw = source_path.read_bytes()
        actual = hashlib.sha256(raw).hexdigest()
        if expected.get(source_name) != actual:
            print(
                f"SHA256 MISMATCH for {source_name}\n"
                f"  manifest {expected.get(source_name)}\n  actual   {actual}",
                file=sys.stderr,
            )
            return 1

        panel = extract_panel(raw.decode("utf-8"), source_name)
        out = DEST / derived_name
        out.write_bytes(panel.encode("utf-8"))
        rows.append(
            (
                source_name,
                actual,
                derived_name,
                hashlib.sha256(out.read_bytes()).hexdigest(),
                len(panel.encode("utf-8")),
            )
        )
        print(f"{source_name} -> {derived_name} ({len(panel.encode('utf-8')):,} bytes)")

    readme = [
        "# SEC listing fixtures — provenance\n",
        "Derived from the response bodies captured for issue #123 by",
        "`tests/services/sec/derive_th_fixtures.py`, which verifies every source sha256 against the",
        "bundle's `MANIFEST.md` and then slices the result panel out of the original bytes verbatim.",
        "Nothing here was re-encoded, reformatted or Unicode-normalized, so the Thai text is exactly",
        "what the server sent.\n",
        "The captured bodies carry **no charset declaration** (the site sends it in the",
        "`Content-Type` header, which the capture recorded no headers for). None was invented: these",
        "files are UTF-8 and the tests decode them explicitly as UTF-8, which is what",
        "`AsyncDataFetcher` does with the live response.\n",
        "Regenerate with:\n",
        "```bash",
        "uv run python tests/services/sec/derive_th_fixtures.py tmp/issue-123-bundle",
        "```\n",
        "| Source (bundle) | Source sha256 | Derived | Derived sha256 | Bytes |",
        "|---|---|---|---|---|",
    ]
    for src, src_hash, dst, dst_hash, size in rows:
        readme.append(f"| `{src}` | `{src_hash}` | `{dst}` | `{dst_hash}` | {size:,} |")
    readme.append("")
    (DEST / "README.md").write_text("\n".join(readme), encoding="utf-8")
    print(f"wrote {DEST / 'README.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
