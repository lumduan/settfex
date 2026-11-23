# Bank of Thailand API fixtures (settfex 1.0.0)

Captured live from `https://gateway.api.bot.or.th` on **2026-11-23, 11:30-11:58 ICT**, with the
operator's own per-product tokens. Each body is the API's JSON, **trimmed** so the tests read:
`data_detail`, `category`, `series_details`, holiday lists and the license `ResultSet` keep their
first 2-3 entries, and `observations` keep their last 3. Values are verbatim. No body carries a
token (checked: 0 matches). The license-check records are the BOT's public registry entries.

| File | Endpoint |
|---|---|
| `policy_rate.json` | `PolicyRate/v3/policy_rate/` |
| `bibor_avg_rate.json`, `bibor_rate.json` | `BIBOR/v2/bibor_avg_rate/`, `/bibor_rate/` (2026-11-16..20) |
| `deposit_rate.json`, `avg_deposit_rate.json` | `DepositRate/v2/...` |
| `loan_rate.json`, `avg_loan_rate.json` | `LoanRate/v2/...` |
| `interbank_txn_rate.json` | `Stat-InterbankTransactionRate/v2/INTRBNK_TXN_RATE/` |
| `ext_int_rate.json`, `spot_rate.json`, `swap_point.json`, `thb_implied_rate.json` | the four tables empty since 2024-12-27 |
| `daily_avg_exg_rate.json`, `monthly_ref_rate.json` | `Stat-ExchangeRate/v2/DAILY_AVG_EXG_RATE/`, `Stat-ReferenceRate/v2/MONTHLY_REF_RATE/` |
| `bond_auction.json` | `BondAuction/bond_auction_v2/` (2026-11-01..20) |
| `fi_holidays.json` | `financial-institutions-holidays/?year=2026` |
| `category_list.json`, `series_list.json`, `search_series_bond_yield.json` | Statistics metadata |
| `obs_thor_avg_3m.json`, `obs_gov_6m_monthly.json` | `observations/` (THOR average 3M daily; government yield 6M monthly) |
| `err_obs_badcode.json` | `observations/?series_code=NOSUCHSERIES000`: HTTP 200, every field null |
| `license_search.json`, `license_detail.json` | `BotLicenseCheckAPI/SearchAuthorized`, `/AuthorizedDetail?id=55` |
