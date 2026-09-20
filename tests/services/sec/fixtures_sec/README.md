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
