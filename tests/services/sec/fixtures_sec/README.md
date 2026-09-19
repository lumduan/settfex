# SEC listing fixtures — provenance

Derived from the response bodies captured for issue #123 by
`tests/services/sec/derive_th_fixtures.py`, which verifies every source sha256 against the
bundle's `MANIFEST.md` and then slices the result panel out of the original bytes verbatim.
Nothing here was re-encoded, reformatted or Unicode-normalized, so the Thai text is exactly
what the server sent.

The captured bodies carry **no charset declaration** (the site sends it in the
`Content-Type` header, which the capture recorded no headers for). None was invented: these
files are UTF-8 and the tests decode them explicitly as UTF-8, which is what
`AsyncDataFetcher` does with the live response.

Regenerate with:

```bash
uv run python tests/services/sec/derive_th_fixtures.py tmp/issue-123-bundle
```

| Source (bundle) | Source sha256 | Derived | Derived sha256 | Bytes |
|---|---|---|---|---|
| `E3_th_PTT_FS_20250101-20250630.html` | `ceefbaada6a833441f4028454a7aaa4c5330cd127c8c6d5b8c8bec092b17959a` | `th_ptt_fs_h1_2025.html` | `b96d395313971350bb3fbd53ddbdbe0de22a33ffadcaf1a799a7fbe76d03e378` | 9,828 |
| `E4_en_PTT_FS_20250101-20250630.html` | `de51928a51642b4ce2af0788d6d7eb54b3cef20e67b9efa3b89bee7a6207620b` | `en_ptt_fs_h1_2025.html` | `973ef0ef9174dc974414e1aa554883cbdb6b1f15f0d65ceb63eff01243722516` | 7,827 |
| `E9_th_MOTHER_FS_20250101-20250630.html` | `25d262627104612932b58420a189471f682e2b8a396421d2f205573337236f9f` | `th_mother_fs_h1_2025.html` | `53e0fbf0a0c0fc055af3b0d044e503060996eb5a0f9eebafed25ee82dda246e8` | 8,205 |
| `E10_en_MOTHER_FS_20250101-20250630.html` | `412be67f5e6cf0d17d5788d3a052becf529d857e6cacd796bc5182c44a552ee7` | `en_mother_fs_h1_2025.html` | `f8080703bd2deab3d37528b2d796c807fdb5a904500fc6269a5d42974be8a3a5` | 6,123 |
