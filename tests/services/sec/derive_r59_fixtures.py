#!/usr/bin/env python3
"""Derive the committed Form 59 (r59) fixtures from the 2026-10-07 probe bundle.

Run from the repo root, with the bundle extracted somewhere gitignored::

    uv run python tests/services/sec/derive_r59_fixtures.py tmp/r59-bundle

* Every source's sha256 is checked against the bundle's ``MANIFEST.md`` (the probe's own
  per-request record) before anything is written. A mismatch aborts.
* **panel**: the result panel ``<div id="ctl00_CPH_pnlControl">…</div>`` sliced VERBATIM, a byte
  range of the original; the ASP.NET token blobs, the 935-option company dropdown and the chrome
  are dropped. Nothing is re-encoded or normalized.
* **verbatim**: the whole body, unchanged (the detail JSON, the small empty ViewMore page).
* **assembled**: NOT a server response. The empty ViewMore panel (#135) as the skeleton, its
  "no data" row replaced by ``<tr>`` elements sliced verbatim from a capture, and its stated count
  replaced by the number of rows inserted. Used where the rows worth testing are scattered across
  a 70 MB page; each inserted row is still byte-for-byte what the server sent.

Rerunning must produce a zero git diff: every output is a pure function of the source bytes.
"""

from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path

DEST = Path(__file__).parent / "fixtures_sec" / "r59"
PANEL_START = '<div id="ctl00_CPH_pnlControl"'
EMPTY_ROW = '<tr><td colspan="9">ไม่พบข้อมูล</td></tr>'
EMPTY_COUNT = "(จำนวนรายการที่พบ 0 รายการ)"

# (source in the bundle, derived name, mode, why)
SELECTED = [
    (
        "004_B_th_spali_txn_0109_0710.html",
        "th_spali_txn_202609.html",
        "panel",
        "SPALI spouse duplicates: 12 pairs, reporters 12061/12062, one executor",
    ),
    (
        "008_B_th_kcg_txn_0109_0710.html",
        "th_kcg_txn_202609.html",
        "panel",
        "KCG self + TEMP_P_ spouse rows: identical-looking, separate trades",
    ),
    (
        "005_B_th_all_rcv_0210.html",
        "th_capped_rcv_20261002.html",
        "panel",
        "postback page capped at 100 rows while stating 112; must be refused",
    ),
    (
        "135_D_th_vm_direct_SPALI_txn_empty.html",
        "th_empty.html",
        "verbatim",
        "empty ViewMore page: count 0 + the no-data row",
    ),
    (
        "001_A_th_default.html",
        "th_default_20261007.html",
        "panel",
        "the site's default page, Thai (27 rows)",
    ),
    (
        "002_A_en_default.html",
        "en_default_20261007.html",
        "panel",
        "the same 27 rows in English: C.E. dates, English labels",
    ),
]
DETAILS = {
    # batch -> (source, why)
    "592001352610": ("196_P_th_dtcent_592001352610.json", "DTCENT: the human-verified reference"),
    "592000452610": ("159_E3_th_sameday_PEACE.json", "PEACE: 53 transactions, a '*' holding"),
    "592000392610": ("158_E3_th_transfer_out_HENG.json", "HENG: off-market transfer to children"),
    "592000522610": ("157_E3_th_revoked_MRDIYT.json", "MRDIYT: a revoked batch"),
    "592005512609": ("160_E3_th_trust_unit_WHAIR.json", "WHAIR: trust units"),
    "592001432610": ("152_E3_th_self_buy_CTW.json", "CTW: a self buy (th)"),
    "592002622609": ("155_E3_th_kcg_self_1409.json", "KCG self 14/09"),
    "592002632609": ("156_E3_th_kcg_spouse_1409.json", "KCG spouse 14/09"),
    "592001242610": ("170_P_th_p3_592001242610.json", "CREDIT spouse rows (EDITED/CANCELED)"),
    "592000142610": ("166_P_th_p3_592000142610.json", "CREDIT reporter's own 09/09 row"),
    "592004052609": ("185_P_th_p3_592004052609.json", "STX, reporter 173156"),
    "592004042609": ("184_P_th_p3_592004042609.json", "STX, reporter 186394"),
    # The SPALI listing's batches that were captured (12 of 14; 592000892610 / 592000902610 not).
    "592000082610": ("154_E3_th_spali_twin_12062.json", "SPALI"),
    "592000092610": ("153_E3_th_spali_dup_12061.json", "SPALI"),
    "592002772609": ("174_P_th_p3_592002772609.json", "SPALI"),
    "592002782609": ("175_P_th_p3_592002782609.json", "SPALI"),
    "592003452609": ("180_P_th_p3_592003452609.json", "SPALI"),
    "592003462609": ("181_P_th_p3_592003462609.json", "SPALI"),
    "592004192609": ("186_P_th_p3_592004192609.json", "SPALI"),
    "592004202609": ("187_P_th_p3_592004202609.json", "SPALI"),
    "592004532609": ("188_P_th_p3_592004532609.json", "SPALI"),
    "592004542609": ("189_P_th_p3_592004542609.json", "SPALI"),
    "592004992609": ("192_P_th_p3_592004992609.json", "SPALI"),
    "592005002609": ("193_P_th_p3_592005002609.json", "SPALI"),
}
EN_DETAILS = {"592001432610": ("161_E3_en_self_buy_CTW.json", "CTW: the same batch in English")}

# Assembled pages: (derived name, source page, row selectors, why). A selector is a transId, or a
# text snippet whose FIRST occurrence picks the row.
ASSEMBLED = [
    (
        "th_edge_rows.html",
        "163_E4_th_vm_r59-2_bare.html",
        [
            "165152_2_1",
            "165153_3_3",
            "124877_2_1",
            "124558_2_1",
            "113332_2_1",
            "124623_2_1",
            "165253_2_1",
            "163814_2_2",
            "124630_2_1",
            "162688_2_1",
            "103283_2_1",
            "165135_2_1",
            ">29/02/2567<",
            "(BANPU ยุติ)",
            ">แก้ไขข้อมูล",
            ">ทำรายการโดย",
            ">ผู้จัดทำ<",
            ">แปลงจาก NVDR<",
            ">รับโอน-คืนจากผู้รับฝาก<",
            ">ขาย-เพื่อผู้ฝาก<",
            ">ใบสำคัญแสดงสิทธิที่จะซื้อหุ้น2<",
            ">0.00<",
            'executor=CTRL_C_ "',
        ],
        "one row per edge the full history holds (revoked, '-' and 0.00 prices, 0 quantity, empty "
        "date, no link, blank ids, B.E. leap day, rare labels)",
    ),
    (
        "th_sep_pairs.html",
        "016_C1_th_vm_all_txn_1m_202609.html",
        [
            "164754_2_1",
            "164755_2_1",
            "165100_2_1",
            "165102_2_1",
            "165233_2_1",
            "165109_2_1",
            "164897_2_1",
            "164899_2_1",
        ],
        "the September duplicate classes: KCG (separate), SPALI (copy), CREDIT (holdings equal, "
        "ids differ), STX (one company executor, two reporters, holdings differ)",
    ),
]


def manifest(bundle: Path) -> dict[str, str]:
    """file -> sha256, from the probe's MANIFEST.md table (sha in column 10, file in column 11)."""
    found: dict[str, str] = {}
    for line in (bundle / "MANIFEST.md").read_text(encoding="utf-8").splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) == 11 and cells[0].isdigit():
            found[cells[10]] = cells[9]
    return found


def read_verified(bundle: Path, name: str, hashes: dict[str, str]) -> bytes:
    raw = (bundle / name).read_bytes()
    if hashes.get(name) != hashlib.sha256(raw).hexdigest():
        raise SystemExit(f"{name}: sha256 does not match MANIFEST.md")
    return raw


def panel(html: str, source: str) -> str:
    start = html.find(PANEL_START)
    if start < 0:
        raise SystemExit(f"{source}: no {PANEL_START!r}")
    depth = 0
    for match in re.finditer(r"<div\b|</div>", html[start:]):
        depth += 1 if match.group(0) == "<div" else -1
        if depth == 0:
            return html[start : start + match.end()]
    raise SystemExit(f"{source}: unbalanced <div> after the result panel")


def row_at(html: str, selector: str, source: str) -> str:
    needle = f"transId={selector}&" if re.fullmatch(r"\d+_\d+_\d+", selector) else selector
    at = html.find(needle)
    if at < 0:
        raise SystemExit(f"{source}: no row for {selector!r}")
    start = html.rfind("<tr>", 0, at)
    end = html.find("</tr>", at) + len("</tr>")
    row = html[start:end]
    if row.count("<td") != 9:
        raise SystemExit(f"{source}: row for {selector!r} does not have 9 cells")
    return row


def main(argv: list[str]) -> int:
    bundle = Path(argv[1] if len(argv) > 1 else "tmp/r59-bundle")
    hashes = manifest(bundle)
    DEST.mkdir(parents=True, exist_ok=True)
    out: list[tuple[str, str, str, str, int, str]] = []

    def write(name: str, data: bytes, source: str, mode: str) -> None:
        (DEST / name).write_bytes(data)
        out.append(
            (source, hashes[source], name, hashlib.sha256(data).hexdigest(), len(data), mode)
        )

    for source, name, mode, _ in SELECTED:
        raw = read_verified(bundle, source, hashes)
        data = raw if mode == "verbatim" else panel(raw.decode("utf-8"), source).encode("utf-8")
        write(name, data, source, mode)

    skeleton = panel(
        read_verified(bundle, "135_D_th_vm_direct_SPALI_txn_empty.html", hashes).decode("utf-8"),
        "135",
    )
    for name, source, selectors, _ in ASSEMBLED:
        html = read_verified(bundle, source, hashes).decode("utf-8")
        picked: list[str] = []
        for selector in selectors:
            row = row_at(html, selector, source)
            if row not in picked:
                picked.append(row)
        page = skeleton.replace(EMPTY_ROW, "".join(picked)).replace(
            EMPTY_COUNT, f"(จำนวนรายการที่พบ {len(picked)} รายการ)"
        )
        write(name, page.encode("utf-8"), source, f"assembled ({len(picked)} rows)")

    for lang, table in (("th", DETAILS), ("en", EN_DETAILS)):
        for batch, (source, _) in table.items():
            write(
                f"detail_{batch}_{lang}.json",
                read_verified(bundle, source, hashes),
                source,
                "verbatim",
            )

    print(
        "| Source (r59-bundle) | Source sha256 | Derived (`r59/`) | Derived sha256 | Bytes | Mode |"
    )
    print("|---|---|---|---|---|---|")
    for source, s_hash, name, d_hash, size, mode in out:
        print(f"| `{source}` | `{s_hash}` | `{name}` | `{d_hash}` | {size:,} | {mode} |")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
