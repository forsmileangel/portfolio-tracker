# 派網網格 × Gist 契約（Portfolio Tracker）

改 Portfolio Tracker 的 Gist pull、網格分頁、或加密 TWD 填入之前，先讀這份。帳本是 **SQLite 本機儀表板** 寫上同一私有 Gist 的第二檔；這裡只讀。改壞驗證或檔名，網格頁會空白。

完整欄位與禁止事項以 SQLite 專案為準：

`D:\My-project\pionex grid record-v2\PORTFOLIO-TRACKER-GIST.md`

## 這側不能動的硬條件

- 日記帳檔名必須是 `pionex-grid-ledger.json`（`GIST_LEDGER_FILENAME`）。
- 目前倉位檔名必須是 `pionex-grid-live.json`（`GIST_LIVE_FILENAME`，v15.962）。`_validatePionexLive` 要求 `schema === 1` 且 `rows` 是陣列。失敗只空白「目前倉位」區。
- `_validatePionexLedger` 現在要求 `schema === 1` 且 `days` 是陣列。加嚴驗證前，確認 SQLite 的 `ledger_publish_payload()` 已有那些欄位。
- 讀失敗要保留舊 cache，**不可**讓持倉 Gist 同步跟著失敗。
- **不要 PATCH** `pionex-grid-ledger.json` 或 `pionex-grid-live.json`。**不要**把派網 API 金鑰放進 PT。
- 不要改第一檔 `portfolio-tracker-holdings.json` 的寫入流程來遷就網格帳本。

## 這側正在讀的欄位

`days[].date`、`daily_profit_usdt`、`cumulative_usdt`、可選 TWD；`wallet.twd` 給「填入加密欄」；`capture_date`／`captured_at` 給新鮮度。

SQLite 後來加的 `true_profit_*` 目前可忽略；若網格月曆要顯示「真實總利潤」，再讀這些 key，不要因此把 `schema` 改成 2 除非兩邊同一天改。
