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

`days[].date`、`daily_profit_usdt`、`cumulative_usdt`、可選 TWD；`wallet.twd` 給「填入加密欄」；`capture_date`／`captured_at` 給新鮮度。帳本另讀 `days[].funding_usdt`／`net_usdt`／`funding_span_days`／`funding_total_usdt`（資金費未知時 `net_usdt` 為 null）。網格分頁的單日與月平均以淨利（配對＋資金費）為主；淨利算不出時退回配對並標示。

SQLite 後來加的 `true_profit_*` 目前可忽略；若網格月曆要顯示「真實總利潤」，再讀這些 key，不要因此把 `schema` 改成 2 除非兩邊同一天改。

## 目前倉位 24 小時淨利（v2 1.0.7 起，可選，schema 仍為 1）

本機 v2 1.0.7 起在 `pionex-grid-live.json` **只加欄位**，`schema` 維持 1。舊檔沒有這些欄位時，PT 退回 `total_profit_24h_usdt`／`profit_24h_pct` 與列上的 `profit_24h_usdt`，並標示暫不含資金費。不要為了這些欄位把 `schema` 改成 2。

頂層（可選）：

- `total_funding_24h_usdt`：目前倉位近 24 小時資金費合計。付出為負、收到為正。
- `total_net_24h_usdt`：近 24 小時淨利，等於配對加上資金費。
- `net_24h_pct`：淨利除以等效倉位的百分比。有這欄時取代 `profit_24h_pct` 當作 24h 百分比。
- `funding_24h_missing`：缺資金費資料的倉位數。大於 0 時 `total_net_24h_usdt` 為 null，畫面退回配對並註明。
- `funding_24h_pending`：派網在 00:00／08:00／16:00 結算後幾分鐘才入帳。這段時間內還沒入帳的倉位數；淨利照算，只是那幾倉最新一次結算先不計，畫面註明。

每列 `rows[]`（可選）：

- `funding_24h_usdt`
- `net_24h_usdt`：有數字時，該列 24h 與排序用這個值；沒有則退回 `profit_24h_usdt`。
