# SEC listing fixtures — provenance

Derived from the response bodies captured for issues #123, #127, #131, #133 and the
0.22.2 slug fix by
`tests/services/sec/derive_th_fixtures.py`, which verifies every source sha256 against the
bundle's `MANIFEST.md` and then either slices the result panel out of the original bytes
or copies the whole body, verbatim in both cases.
Nothing here was re-encoded, reformatted or Unicode-normalized, so the Thai text is exactly
what the server sent.

The captured bodies carry **no charset declaration** (the site sends it in the
`Content-Type` header, which the capture recorded no headers for). None was invented: these
files are UTF-8 and the tests decode them explicitly as UTF-8, which is what
`AsyncDataFetcher` does with the live response.

Regenerate with:

```bash
uv run python tests/services/sec/derive_th_fixtures.py \
    tmp/issue-123-bundle tmp/issue-127-bundle
```

| Issue | Source (bundle) | Source sha256 | Derived | Derived sha256 | Bytes |
|---|---|---|---|---|---|
| #123 | `E3_th_PTT_FS_20250101-20250630.html` | `ceefbaada6a833441f4028454a7aaa4c5330cd127c8c6d5b8c8bec092b17959a` | `th_ptt_fs_h1_2025.html` | `b96d395313971350bb3fbd53ddbdbe0de22a33ffadcaf1a799a7fbe76d03e378` | 9,828 |
| #123 | `E4_en_PTT_FS_20250101-20250630.html` | `de51928a51642b4ce2af0788d6d7eb54b3cef20e67b9efa3b89bee7a6207620b` | `en_ptt_fs_h1_2025.html` | `973ef0ef9174dc974414e1aa554883cbdb6b1f15f0d65ceb63eff01243722516` | 7,827 |
| #123 | `E9_th_MOTHER_FS_20250101-20250630.html` | `25d262627104612932b58420a189471f682e2b8a396421d2f205573337236f9f` | `th_mother_fs_h1_2025.html` | `53e0fbf0a0c0fc055af3b0d044e503060996eb5a0f9eebafed25ee82dda246e8` | 8,205 |
| #123 | `E10_en_MOTHER_FS_20250101-20250630.html` | `412be67f5e6cf0d17d5788d3a052becf529d857e6cacd796bc5182c44a552ee7` | `en_mother_fs_h1_2025.html` | `f8080703bd2deab3d37528b2d796c807fdb5a904500fc6269a5d42974be8a3a5` | 6,123 |
| #127 | `F1_th_PTT_56-1.html` | `44ce95f1dab9763b97e2c2dc0c4baf403ae93f3a71b4550eece921e314d89d50` | `th_ptt_56_1.html` | `250141b38fc8809afdb9d9ece5012970b3a78705604e5b8ea80e0fc4e5f90ad9` | 2,861 |
| #127 | `F2_en_PTT_56-1.html` | `20d7949f8e7872efd70a2a336489c12addddbbf4a85e127fe2609a53dd979b75` | `en_ptt_56_1.html` | `dc4ecce003d1ea9a9d8e3a4d219b8a619b5d1f399e8e9214db867988c041b4b1` | 3,334 |
| #127 | `F5_th_PTT_56-2.html` | `550c78c591164532594dc86adaa1ebd9ade607af18b568159bde54da33d13692` | `th_ptt_56_2.html` | `3942d4f3ab8604ec1445b35b869723a8ed8b88d922bdbc19a5071e8ef9e63e03` | 3,476 |
| #127 | `F3_en_PTT_56-2.html` | `0be33ee80ad2ec303d699d74d1b9d6ba8fbd5cff33fd0b557e825827deb1548a` | `en_ptt_56_2.html` | `84cec174807540f4e03cdc7a2853bcb96a65a58d2ae5f6293c64e12f6bf64ae1` | 3,056 |
| #131 | `G5_idisc_505_error_page.html` | `3c6c080037bc084f14cb1cd2a89c09698dd00ad831e2efb0d553618b051d2794` | `idisc_505_error_page.html` | `3c6c080037bc084f14cb1cd2a89c09698dd00ad831e2efb0d553618b051d2794` | 369 |
| #133 | `G2_capital_indirection_en_2013_p12.html` | `e0e114533be26b36e796880130ce4b3650f20122d0f4164a838faf93498ff35f` | `capital_indirection_en.html` | `e0e114533be26b36e796880130ce4b3650f20122d0f4164a838faf93498ff35f` | 2,263 |
| 0.22.2 | `H1_th_CPALL_viewmore_fs-r561.html` | `c413c1ce84e12315a01f80fdd6db8d478102d206412916eff7d48e958f36c622` | `th_cpall_viewmore_56_1.html` | `2756b5585f08b761bf3c93a2dc36b2d525f43457223d3004b438695056ba7f9c` | 5,640 |
| 0.22.2 | `H2_en_PTT_viewmore_fs-r562.html` | `c54c4b883c7e48193d254f3cea4735b5b23f1cd2c3bac7ae7d7b80814eac880e` | `en_ptt_viewmore_56_2.html` | `4880199be20a556cb3bb69840a694beeb6e9d42b7b1ae4c157e2c2e341a03c10` | 5,857 |

## Form 59 (`r59/`) — derived from the 2026-10-07 probe bundle

Derived by `tests/services/sec/derive_r59_fixtures.py` from `tmp/r59-bundle/` (the GATE A probe
of the Form 59 listing and its detail API; 196 requests, all HTTP 200). The script checks every
source against the bundle's own `MANIFEST.md` before writing. Three modes:

* **panel**: the `ctl00_CPH_pnlControl` result panel sliced verbatim (the 152 KB `__VIEWSTATE`
  and the 935-option company dropdown are dropped);
* **verbatim**: the whole response body (detail JSON, the small empty ViewMore page);
* **assembled**: **not a server response**. The empty ViewMore panel (#135) is the skeleton; its
  "ไม่พบข้อมูล" (no data) row is replaced by `<tr>` rows sliced verbatim from the named capture,
  and its stated count is set to the number of rows inserted. Used where the rows worth testing
  are scattered over a 70 MB page. Each inserted row is byte-for-byte what the server sent; the
  selectors (transIds or text snippets) are listed in the script.

Regenerate with:

```bash
uv run python tests/services/sec/derive_r59_fixtures.py tmp/r59-bundle
```

| Source (r59-bundle) | Source sha256 | Derived (`r59/`) | Derived sha256 | Bytes | Mode |
|---|---|---|---|---|---|
| `004_B_th_spali_txn_0109_0710.html` | `973faf60c9b1227662b3e7ff23eb75767063dc9290ee79a690e409429f554fc6` | `th_spali_txn_202609.html` | `075999d2062bdcc93c11af5c3e6a46a22520cf856f05f1f9c8b341302e2b1ea3` | 21,953 | panel |
| `008_B_th_kcg_txn_0109_0710.html` | `193fd190bea544595157591e3c590e543220a3ca716d93bc624b68f4140615c4` | `th_kcg_txn_202609.html` | `6d039bb2715dd116957e13cf8119cb4f403a3dcbb8fbb1d52ec5797864a747c0` | 28,183 | panel |
| `005_B_th_all_rcv_0210.html` | `f50c3cd905e244afcba9e661102c114f30a674c2feeaf8cf81699d6a85e4e10c` | `th_capped_rcv_20261002.html` | `2431bd69508d86e6b9af33a90d46e25a844e7f4c1068ab9b2c21b7b41faa614a` | 83,366 | panel |
| `135_D_th_vm_direct_SPALI_txn_empty.html` | `65beed8663ba4224a5d75d012a65bc3e7a5a460024d449c760d93c24edc9b68f` | `th_empty.html` | `65beed8663ba4224a5d75d012a65bc3e7a5a460024d449c760d93c24edc9b68f` | 9,790 | verbatim |
| `001_A_th_default.html` | `4e3850c3293f12030b8a3c6ded0bee245caeeaadb819cc927154b4b27195c044` | `th_default_20261007.html` | `01fc5918fc130bdb03a9c77809b37c46cfa36e3971bd26ecfebaf40514f2e37e` | 23,674 | panel |
| `002_A_en_default.html` | `1646a3c82d0f316153a8c327bbc1c5f72534509bbaa26bb06871983f4ace3704` | `en_default_20261007.html` | `3c49c8fb3e04cd330e3ae420709075366457c0aca62d308588558f0f51ab0e1c` | 18,012 | panel |
| `163_E4_th_vm_r59-2_bare.html` | `cd745d9ec01e9a812a8156ba3ad8cafabfcac6cee53859b6433f2e9f56fd6e5a` | `th_edge_rows.html` | `729a3b34e359c528b8b3d7b96b2693284c45f191359bf6e7538b5623867d1e19` | 20,856 | assembled (22 rows) |
| `018_C1_th_vm_all_txn_3m_0807_0710.html` | `76669a694955b45102e6c1fc3e9ff261a112437c1dfa87a69dfb513c4c4129c5` | `th_sep_pairs.html` | `09dcec238ffbbeac3a946fd43f2b3135a2264d9d056ef5d9eba8e7ecced67562` | 57,661 | assembled (58 rows) |
| `196_P_th_dtcent_592001352610.json` | `c8453be6ec242f842d65ba3f01ffc39ede2801fd02a36fa57d9f259d2288a8f7` | `detail_592001352610_th.json` | `c8453be6ec242f842d65ba3f01ffc39ede2801fd02a36fa57d9f259d2288a8f7` | 1,062 | verbatim |
| `159_E3_th_sameday_PEACE.json` | `4b97de16ceb656c2a936d3303538d2ae6d513b22ab34ca7061263ccd58fbd9d0` | `detail_592000452610_th.json` | `4b97de16ceb656c2a936d3303538d2ae6d513b22ab34ca7061263ccd58fbd9d0` | 37,411 | verbatim |
| `158_E3_th_transfer_out_HENG.json` | `de87c41892c11b89082bd90fc909440fd6b8c2ff0ecf03ad57573efdb3c1c9fc` | `detail_592000392610_th.json` | `de87c41892c11b89082bd90fc909440fd6b8c2ff0ecf03ad57573efdb3c1c9fc` | 1,246 | verbatim |
| `157_E3_th_revoked_MRDIYT.json` | `9afdfd810458633553db0b05bf80fa66512ee6fb14ff6f2a565dc1edcdd7a32f` | `detail_592000522610_th.json` | `9afdfd810458633553db0b05bf80fa66512ee6fb14ff6f2a565dc1edcdd7a32f` | 2,042 | verbatim |
| `160_E3_th_trust_unit_WHAIR.json` | `d87135a059ec4ed8f789921bdfbff0e7afd3aaacccc7a1bd5f9d0d6bfacd6ebe` | `detail_592005512609_th.json` | `d87135a059ec4ed8f789921bdfbff0e7afd3aaacccc7a1bd5f9d0d6bfacd6ebe` | 1,143 | verbatim |
| `152_E3_th_self_buy_CTW.json` | `418fcd1d28818f00ccec64ce97645c255b32129a34feac3988a64d2a07440908` | `detail_592001432610_th.json` | `418fcd1d28818f00ccec64ce97645c255b32129a34feac3988a64d2a07440908` | 999 | verbatim |
| `155_E3_th_kcg_self_1409.json` | `d9eb20708c1676642e66119b9a165bbe31b16d2af90ec32261446f7c2bcb380f` | `detail_592002622609_th.json` | `d9eb20708c1676642e66119b9a165bbe31b16d2af90ec32261446f7c2bcb380f` | 993 | verbatim |
| `156_E3_th_kcg_spouse_1409.json` | `3648da075b36bce38eaeeac965d8db727b192b35706b71a3957253006f62114c` | `detail_592002632609_th.json` | `3648da075b36bce38eaeeac965d8db727b192b35706b71a3957253006f62114c` | 1,151 | verbatim |
| `170_P_th_p3_592001242610.json` | `8f0d7989de46632e9743088f6b5bc0acd6515022ae5ef345c8ba7b427d1c9915` | `detail_592001242610_th.json` | `8f0d7989de46632e9743088f6b5bc0acd6515022ae5ef345c8ba7b427d1c9915` | 3,245 | verbatim |
| `166_P_th_p3_592000142610.json` | `283e7b163592d810c73a0c111fe15cb6b75eaffbdf87d08353da1c5d4279d241` | `detail_592000142610_th.json` | `283e7b163592d810c73a0c111fe15cb6b75eaffbdf87d08353da1c5d4279d241` | 1,007 | verbatim |
| `185_P_th_p3_592004052609.json` | `63fec9934a304f509b7369401861faf748cdb04291fdf8658e892e3fdf4be068` | `detail_592004052609_th.json` | `63fec9934a304f509b7369401861faf748cdb04291fdf8658e892e3fdf4be068` | 3,785 | verbatim |
| `184_P_th_p3_592004042609.json` | `df69037f5c2ba6c4d8616ab9c33be12fde714743e93d176276cfaca4d3f80a72` | `detail_592004042609_th.json` | `df69037f5c2ba6c4d8616ab9c33be12fde714743e93d176276cfaca4d3f80a72` | 3,779 | verbatim |
| `165_P_th_p3_592000102610.json` | `c525dbff1e0d623935c3ae4ec55ed4df61e023075615b369523c97951a2b33fe` | `detail_592000102610_th.json` | `c525dbff1e0d623935c3ae4ec55ed4df61e023075615b369523c97951a2b33fe` | 1,137 | verbatim |
| `167_P_th_p3_592000152610.json` | `c5d5864c831d30e7d9b11c3db4239c5677529c0648c9d939dd7b1064c0210468` | `detail_592000152610_th.json` | `c5d5864c831d30e7d9b11c3db4239c5677529c0648c9d939dd7b1064c0210468` | 1,011 | verbatim |
| `168_P_th_p3_592000532609.json` | `43dfabe754e31494aebecb27d05994f417a88bea225c176480b5598c95286294` | `detail_592000532609_th.json` | `43dfabe754e31494aebecb27d05994f417a88bea225c176480b5598c95286294` | 994 | verbatim |
| `169_P_th_p3_592000542609.json` | `6fb2240307d9889030bc939c95cdb833e94fafee17b7131cec3abfc12f567bc0` | `detail_592000542609_th.json` | `6fb2240307d9889030bc939c95cdb833e94fafee17b7131cec3abfc12f567bc0` | 1,152 | verbatim |
| `171_P_th_p3_592001262610.json` | `96f7c4039167078e2f06e6ef35ea29b1e72db3ae08b9abbccabc5d67b2982dd4` | `detail_592001262610_th.json` | `96f7c4039167078e2f06e6ef35ea29b1e72db3ae08b9abbccabc5d67b2982dd4` | 1,831 | verbatim |
| `172_P_th_p3_592001352609.json` | `12de10189c99ad5a4a2de42225963bcd5a9f9b7f3eaf9387c1a8baeb524ac1e8` | `detail_592001352609_th.json` | `12de10189c99ad5a4a2de42225963bcd5a9f9b7f3eaf9387c1a8baeb524ac1e8` | 994 | verbatim |
| `173_P_th_p3_592001372609.json` | `bb9e79a7f0a8fdba8c75705a1e4c8546ba6d53d961edff6250e03dcecc451707` | `detail_592001372609_th.json` | `bb9e79a7f0a8fdba8c75705a1e4c8546ba6d53d961edff6250e03dcecc451707` | 1,152 | verbatim |
| `176_P_th_p3_592002882609.json` | `f8e530e323cacd27f68e54495eb859e039bf8d83c14ff019ac0d35e58dd2912e` | `detail_592002882609_th.json` | `f8e530e323cacd27f68e54495eb859e039bf8d83c14ff019ac0d35e58dd2912e` | 994 | verbatim |
| `177_P_th_p3_592002892609.json` | `45d26437670478f707a689055fcba6f5bfc9921cf6434de9808f8cf7fab1768b` | `detail_592002892609_th.json` | `45d26437670478f707a689055fcba6f5bfc9921cf6434de9808f8cf7fab1768b` | 1,152 | verbatim |
| `178_P_th_p3_592003112609.json` | `b1d03bf74a109a7592b8b370d71de113f5bc156a091e86c51d3533cb21580c39` | `detail_592003112609_th.json` | `b1d03bf74a109a7592b8b370d71de113f5bc156a091e86c51d3533cb21580c39` | 995 | verbatim |
| `179_P_th_p3_592003122609.json` | `0c212763f002b1fa48f00575fb6f3b854ae866646eef65e0073adcc212cd7e4a` | `detail_592003122609_th.json` | `0c212763f002b1fa48f00575fb6f3b854ae866646eef65e0073adcc212cd7e4a` | 1,153 | verbatim |
| `182_P_th_p3_592003632609.json` | `a7a8dd109d7e0d1e475d4e5729e843d59b45c2cc0898c3131841690b3a439ed9` | `detail_592003632609_th.json` | `a7a8dd109d7e0d1e475d4e5729e843d59b45c2cc0898c3131841690b3a439ed9` | 994 | verbatim |
| `183_P_th_p3_592003652609.json` | `ff31c7afb3b41e8ff81fbf33dcc316c69cc278b046d967aeef5e0e2d853484e1` | `detail_592003652609_th.json` | `ff31c7afb3b41e8ff81fbf33dcc316c69cc278b046d967aeef5e0e2d853484e1` | 1,152 | verbatim |
| `190_P_th_p3_592004802609.json` | `9ac5ddf2eb9cf8330c0fdc501384063af61c7f00707c7efa6ab31efee797b25e` | `detail_592004802609_th.json` | `9ac5ddf2eb9cf8330c0fdc501384063af61c7f00707c7efa6ab31efee797b25e` | 4,895 | verbatim |
| `191_P_th_p3_592004812609.json` | `5273f30c140c3463a9bacd9b89cfc5809d7d4a6c284bc696eab121712d40cf4e` | `detail_592004812609_th.json` | `5273f30c140c3463a9bacd9b89cfc5809d7d4a6c284bc696eab121712d40cf4e` | 4,889 | verbatim |
| `194_P_th_p3_592005172609.json` | `0bbcd5c71c00a04411dc75a39d02cf06563db73e5dcc83ed6eb99b0a1d775418` | `detail_592005172609_th.json` | `0bbcd5c71c00a04411dc75a39d02cf06563db73e5dcc83ed6eb99b0a1d775418` | 994 | verbatim |
| `195_P_th_p3_592005182609.json` | `bf2b2c2738926ec1aef1778d47d210216d9cccf0db0bc5b252f1d2a468a3f941` | `detail_592005182609_th.json` | `bf2b2c2738926ec1aef1778d47d210216d9cccf0db0bc5b252f1d2a468a3f941` | 1,152 | verbatim |
| `154_E3_th_spali_twin_12062.json` | `057e3e9ca614c0410fab20764d2c1d37a3ac8a2df91cf8bbad1d506c15184d38` | `detail_592000082610_th.json` | `057e3e9ca614c0410fab20764d2c1d37a3ac8a2df91cf8bbad1d506c15184d38` | 2,109 | verbatim |
| `153_E3_th_spali_dup_12061.json` | `9d4fc7ddad64619bb659dce36650c6502e59ec86816ddb9da5a485fd13635230` | `detail_592000092610_th.json` | `9d4fc7ddad64619bb659dce36650c6502e59ec86816ddb9da5a485fd13635230` | 2,598 | verbatim |
| `174_P_th_p3_592002772609.json` | `87cf460ade14c86781662cb476b6e6446fea8b2c158a114470afb5c66e505825` | `detail_592002772609_th.json` | `87cf460ade14c86781662cb476b6e6446fea8b2c158a114470afb5c66e505825` | 1,520 | verbatim |
| `175_P_th_p3_592002782609.json` | `8e93632670259143f722e380aebbc95198fdddc0dfe6a320b2dcc21b52ffe724` | `detail_592002782609_th.json` | `8e93632670259143f722e380aebbc95198fdddc0dfe6a320b2dcc21b52ffe724` | 1,849 | verbatim |
| `180_P_th_p3_592003452609.json` | `d4e4dbfb2686c20158f7447e2a6ff744ee34d16cd951b60e7ca38942b1fb6cca` | `detail_592003452609_th.json` | `d4e4dbfb2686c20158f7447e2a6ff744ee34d16cd951b60e7ca38942b1fb6cca` | 1,017 | verbatim |
| `181_P_th_p3_592003462609.json` | `a9f66518fe2328cdac02efa3d2de22a5d650643fc951d5018e5ae6ef21b0d779` | `detail_592003462609_th.json` | `a9f66518fe2328cdac02efa3d2de22a5d650643fc951d5018e5ae6ef21b0d779` | 1,186 | verbatim |
| `186_P_th_p3_592004192609.json` | `43c8a645b3a55f486a518b4f812112edadd2ffc83b4f09dde3827ddb40a5a240` | `detail_592004192609_th.json` | `43c8a645b3a55f486a518b4f812112edadd2ffc83b4f09dde3827ddb40a5a240` | 1,520 | verbatim |
| `187_P_th_p3_592004202609.json` | `ab930640c915b1673e7e52b3f37f5ca56c61c85c908fb31e3e013789da089d3d` | `detail_592004202609_th.json` | `ab930640c915b1673e7e52b3f37f5ca56c61c85c908fb31e3e013789da089d3d` | 1,849 | verbatim |
| `188_P_th_p3_592004532609.json` | `f15f39a777c67c311309c1c8675ff48c8d34097ff77486e9a680522b542df63b` | `detail_592004532609_th.json` | `f15f39a777c67c311309c1c8675ff48c8d34097ff77486e9a680522b542df63b` | 1,605 | verbatim |
| `189_P_th_p3_592004542609.json` | `b00db7a3562637474fa514d33e3a70567833780d3e80509776e41d73940460c0` | `detail_592004542609_th.json` | `b00db7a3562637474fa514d33e3a70567833780d3e80509776e41d73940460c0` | 1,934 | verbatim |
| `192_P_th_p3_592004992609.json` | `d7a5101c9e077432962a3747f7a1043acb3902d30199ec2629f9987dc66333de` | `detail_592004992609_th.json` | `d7a5101c9e077432962a3747f7a1043acb3902d30199ec2629f9987dc66333de` | 1,059 | verbatim |
| `193_P_th_p3_592005002609.json` | `03ea59329e5614693caf8b70ab4d15fb58b72da1bd7df41c0d9930590d718afa` | `detail_592005002609_th.json` | `03ea59329e5614693caf8b70ab4d15fb58b72da1bd7df41c0d9930590d718afa` | 1,228 | verbatim |
| `161_E3_en_self_buy_CTW.json` | `93962b82493f193ef5e0193fc45a3d5dbd73b5ab9d3e2d6935777816c77851a3` | `detail_592001432610_en.json` | `93962b82493f193ef5e0193fc45a3d5dbd73b5ab9d3e2d6935777816c77851a3` | 714 | verbatim |
