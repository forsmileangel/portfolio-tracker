# Portfolio Tracker — 同步機制不可破壞規則（v15.079 後）

> **這是 Claude / Codex 改 code 前必讀的同步不變式文件。**
>
> v15.069→v15.079 系列每一版都踩同類型的同步坑（snapshot 反覆 push、holdings 直接進 hash、pending fallback 'general'、master id 過早 processed 等），直到 codex review 才被抓到。本文把 11 版踩過的錯誤規律整理成「規則 + 違反案例 + 修改前 checklist」，避免重蹈覆轍。
>
> 涵蓋：Gist / FSA / localStorage / IndexedDB / userDataHash / dirty domains / pending count / marketSnapshots / daily_pnl_snapshots / auto-pull / auto-push / manual push / master flag / rollback / Gist Token / PWA / Android / iPhone。

---

## 1. 核心原則

1. **使用者資料一致性用 `userDataHash` 判斷**，不用 `pushedAt` / `revision` 單獨判斷。
2. **`pushedAt` 是時間順序，不是資料差異**。雲端可能 revision 增加但內容相同（snapshot only push）→ 不可視為使用者 dirty。
3. **system-generated data 不等於 user dirty**。報價 / 分析 / snapshot / FX / cache 都是系統產生，不該觸發使用者可見的「未同步」提示。

---

## 2. User Data Hash 規則

### ✅ 必須包含（使用者真正手動管理的資料）
- `holdings` 結構欄位（id / symbol / market / quantity / costPrice / addedDate / persist / name）
- `lots`（FIFO 成本批次）
- `deposits`
- `tradeHistory`
- `watchlist`
- `currency`
- `sheet_url`
- `cash_pie_cb` / `crypto_twd` / `crypto_pie_cb` / `moxa_twd` / `moxa_pie_cb`

### ❌ 嚴禁包含（任何系統動態欄位）
- 報價：`currentPrice` / `prevClose` / `prevPrevClose` / `dayPnL` / `marketOpenedToday` / `lastQuoteAt`
- 快照：`marketSnapshots` / `daily_pnl_snapshots`
- 快取：`pf_analysis_v*` / fundamentals.json 載入結果
- 中繼：`pushedAt` / `sync_meta` / `Gist revision` / `APP_VERSION`
- FX timestamp / 錯誤日誌

### 強制規則
- **holdings 進 hash 必須走 `_normalizeHoldingForHash()`**，不可直接 `JSON.stringify(holdings)` 或把整個 holding object 丟進 hash 算
- 新增 holdings 欄位時，先決定它是「使用者手動管理」還是「系統自動填入」，前者才加進 `_normalizeHoldingForHash` 白名單

### 違反案例
- **v15.079 初版**：`_buildLocalUserPayload` 直接 `holdings`，沒 normalize → silentRefreshPrices / runAnalysis 寫入 currentPrice 就讓 hash 漂移 → 應該 noop 的 silent push 真的發 PATCH。v15.079 hotfix 加 `_normalizeHoldingsForHash` 修補。

---

## 3. Snapshot 規則

### 設計原則
- `marketSnapshots`（每日總市值快照，月/季/年報酬率分析用）保留
- `daily_pnl_snapshots`（每市場昨日損益快照）保留
- 兩者**有統計與備份意義**，不可移除

### 行為限制
- snapshot **可以**隨真正 user-data push 帶上 Gist payload（payload 內欄位仍在）
- snapshot **不可**單獨 +1 pending count
- snapshot **不可**單獨呼叫 `_gistSilentPush()`
- snapshot **不可**單獨呼叫 `_markAndAutoPush(['marketSnapshots'])` / `_markAndAutoPush(['dailyPnlSnapshots'])`
- 若整個 session 沒任何 user-data 改動，snapshot 就只在本機保存，等下次有 user push 才順帶同步

### 收盤快照前置條件（不可繞過）
- 必須通過 market calendar 檢查（`_isTradingDay(marketKey, target) === true`）
- 必須通過 quote freshness 檢查（`fresh_after_close` 必要條件 = quote meta + analysis meta marketDate **都** === target）
- `pending_quote` 中間狀態本機保留即可，不寫入 dirty / pending

### 違反案例
- **v15.069**：`recordSnapshot()` 寫完 marketSnapshots 直接呼叫 `_gistSilentPush()` → v15.079 hotfix 拔除
- **v15.078**：`fresh_after_close` daily snapshot 仍呼叫 `_markAndAutoPush(['dailyPnlSnapshots'])` → v15.079 hotfix 拔除
- **v15.073 之前**：用 calendar date 當 marketDate → 5/2 週六打開 backfill 把 5/1 勞動節凍進快照
- **v15.078 hotfix 前**：`pending_quote` 寫入時也 mark dirty → PWA 放著就跳「1 筆未同步」

---

## 4. Dirty / Pending 規則

### 兩類 domain 區分
- **user domains**（會影響 UI pending count 與「未同步」提示）：
  - `holdings` / `deposits` / `tradeHistory` / `watchlist` / `settings`
- **system domains**（**不**影響 pending count）：
  - `marketSnapshots` / `dailyPnlSnapshots` / cache / logs

### UI pending count
- 「⚠ N 筆未同步」**只能**代表 user domains
- 顯示邏輯只計入 user domain 的 dirty 標記

### 嚴禁
- ❌ **禁恢復**「`pending > 0 && dirty list empty → ['general']`」fallback
  - 違反案例：v15.079 hotfix 前 `_getDirtyDomains()` 此邏輯讓殘留 pending count 誤判為 user dirty，hash 比對也白費（hash 同但 dirty 不空 → 仍走 dirty 分支）

### Pull 期間 guard
- pull 套用期間 `_isApplyingCloudPull = true`，必須阻止：
  - `_markLocalModified` 反彈標 dirty（renderAll / saveDeposits 內部呼叫會誤觸）
  - `_markAndAutoPush` 排 push timer（pull 完又偷偷 push 排上 Gist revision）
- 違反案例：v15.075 codex P2 漏了 `_markAndAutoPush` 開頭的 guard，v15.075 修補

---

## 5. Push / Pull 規則

### Master flag（`userConfirmedCloudMaster`）
- **只能**由使用者手動點「標記最新版」按鈕產生（`gistPush` master 分支）
- auto-push（`_gistSilentPush`）**永不**寫 master flag
- staging push（手動但不標記主版本）**不**寫 master flag
- master flag 在其他裝置 silent pull 套用後才 `_addProcessedMasterId`
  - **不可**先標 processed 再套用：套用中途 throw 會吃掉 master id，下次啟動就不會 force pull
  - 違反案例：v15.079 初版 `_gistSilentPull` line 4773 先標再套 → hotfix 改成 apply 成功後才標

### Push 模式三選一（手動）
1. **標記最新版**（master）：force PATCH（跳過 preflight reject）+ 寫 master flag + IDB 存 rollback
2. **暫存上傳**（staging）：走 preflight；hash_match 不送 PATCH 只更 baseline；reject 時 confirm 強制覆蓋
3. **取消**（cancel）：直接 return

### silent push
- **永不**強制（`force = true` 只走手動 `gistPush` master 或 staging-confirmed 路徑）
- hash_match 時不送 PATCH，只 `_applySyncBaseline` 更新基準

### Rollback（`rollbackToBeforeMaster`）
- 是「**只還原本機**」操作：
  - 不 PATCH Gist
  - 不影響其他裝置
  - 還原後**必須**標 user dirty（讓 UI 顯示「未同步」）
  - **不可**自動推送（讓使用者選 staging 或再次 master）
- 違反案例：v15.079 初版只還原本機資料，沒標 dirty → 還原後 baseline 仍指 master push 那版，本機與雲端實際不同但顯示 clean。Hotfix 加 `_markDomainsModified` + `pending++` 但不 auto-push。

### Auto-pull
- 啟動時無條件 `_gistSilentPull()`，由 hash-first classify 主導
- hash_match → 只更 baseline，不覆蓋本機
- 未處理 master id → 強制 force apply cloud
- dirty + cloud_newer + hash_diff → reject 並提示

---

## 6. Gist Token / Gist ID 規則

### 兩個獨立位置
- **App / PWA**：每台裝置 localStorage（`STORAGE_KEYS.gistToken` / `STORAGE_KEYS.gistId`）
- **GitHub Actions**：repo secrets（`GIST_TOKEN` / `GIST_ID`），給 SQLite backup workflow + check-tokens workflow 用

### 操作規則
- 換 Token 或新建 Gist 時**兩邊都要更新**
- 任一邊過期會觸發不同症狀：
  - PWA 401 → 前端 toast「Token 失效」+ 停止 retry
  - workflow 401 → check-tokens.yml fail email 通知

### HTTP 401 排錯順序（不要先懷疑同步邏輯）
1. 先檢查 repo secret 是否過期（`Settings → Secrets and variables → Actions`）
2. 再檢查前端 localStorage 內 token（PWA reset / 隱私模式 / iOS 7-day rule）
3. 最後才懷疑同步邏輯本身

---

## 7. PWA / Mobile 規則

### FSA 桌機限定
- `_isFsaSupported()` 三層擋：
  - mobile UA 偵測（Android / iPhone / iPad / Mobile / webOS / BlackBerry / IEMobile / Opera Mini）
  - `window.isSecureContext` 必須為 true
  - `indexedDB` 必須可用
- ❌ **禁用**「全域 first gesture handler 自動 requestPermission」
  - 會搶 Gist 按鈕、攔截 Tab 切換、攔截所有第一次點擊
  - 違反案例：v15.077 init IIFE → user 反映「Android 連基本面頁面都沒辦法切換」→ v15.078 拔除

### 背景 timer 不可製造 user dirty
- `silentRefreshPrices` / `runAnalysis` / FX 更新 / 60 秒 auto refresh 都不該標 user dirty
- hash 不含 currentPrice 等動態欄位即可達成（v15.079 hotfix 已修）

### PWA 版本檢查
- 任何 PWA 自動更新檢查必須 bump `APP_VERSION`，三處同步：
  1. `const APP_VERSION = 'vXX.XXX';`（line ~1037）
  2. 左上角版本字串 `<div ...>vXX.XXX</div>`（line ~381）
  3. changelog 第一行 `vXX.XXX - ...`（line ~84）
- 違反任一處 → PWA 不會偵測到新版

### 跨平台相容
- iOS Safari < 17.4 / 舊 Chrome 缺 API 時必須有 fallback
- 違反案例：v15.064 `AbortSignal.timeout` 直接呼叫 → v15.065 改 try/catch + AbortController + setTimeout 降級

---

## 8. 修改前 Checklist（每次都要對）

改 Gist / FSA / 快照 / pending / hash / PWA 啟動流程任一前，逐項回答 yes/no：

| # | 問題 | 若 yes 該做什麼 |
|---|------|------------------|
| 1 | 這次是否會改 localStorage key？ | 讀 `storage-keys.md` + 設計 migration / rollback 路徑 |
| 2 | 是否會改 Gist payload schema？ | 不升 `PT_SCHEMA_VERSION` 為原則；additive 欄位才 OK |
| 3 | 是否會改 holdings object shape？ | 同步檢查 `_normalizeHoldingForHash` 白名單是否需更新 |
| 4 | 是否會改 `renderAll` / timer / startup 流程？ | 確認不會在 `_isApplyingCloudPull = true` 期間反彈 dirty / push |
| 5 | 是否會讓 system data 進 user hash？ | **禁止**。重新設計 |
| 6 | 是否會讓 system data 進 pending count？ | **禁止**。重新設計 |
| 7 | 是否會讓 pull 後又 auto-push？ | **禁止**。確認 `_isApplyingCloudPull` guard 在 `_markAndAutoPush` 開頭 |
| 8 | 是否影響 Android / iPhone / desktop 三平台？ | FSA 桌機限定；PWA 啟動序列三平台都要過；mobile UA 不能進 FSA path |

---

## 9. v15.069→v15.079 已修補的回歸點（不可重蹈）

| 版本 | 錯誤 | 修補 |
|------|------|------|
| v15.069 | snapshot 結構漏 `quoteStatus` / `lastQuoteAt`，無法判斷新鮮度 | v15.071 補欄位 + `_isQuoteFreshAfterClose` |
| v15.071 | runAnalysis 假冒 quote refresh、CSV 無條件標三市場 | v15.072 移除假呼叫 + 用 `updatedMarkets` Set 累計實際刷到的市場 |
| v15.073 之前 | 用 calendar date 當 marketDate → 週末凍進壞快照 | v15.073 改 market calendar 驅動，target = `lastCompletedTradingDate` |
| v15.074 | `lastCompleteDate` 三市場最舊日壓回 per-market fresh | per-market 各取自己 latest fresh，complete 只看 `_activeMarkets` |
| v15.075 | `_markAndAutoPush` pull 期間反彈排 push timer | 開頭加 `if (_isApplyingCloudPull) return` guard |
| v15.076 | snapshot 寫入沒去重每次 renderAll 都標 dirty + `_shouldRenderPie` 欄位名 bug | 加 `_isSnapshotEquivalent` + 改 `valueTotalTWD` |
| v15.077 | FSA 太寬鬆（Android 也走 FSA） + 全域 capture handler 攔截所有點擊 | v15.078 三層擋桌機限定 + 拔除 handler |
| v15.078 hotfix 前 | `pending_quote` 中間狀態進 dirty | 改 `fresh_after_close` 才標 |
| v15.079 初版 | holdings 直接進 hash + snapshot 仍 auto-push + pending general fallback + rollback 沒標 dirty + master id 過早 processed | hotfix 5 條全修：`_normalizeHoldingsForHash` / 拔 `_markAndAutoPush(['dailyPnlSnapshots'])` / 拔 general fallback / rollback `_markDomainsModified` / `_addProcessedMasterId` 移到 `_applySyncBaseline` 之後 |

---

## 10. 後續修改建議流程

1. 開始改 code 前先讀本檔
2. 對照第 8 章 Checklist 8 條
3. 撰寫 plan 時明確列出本次修改命中哪幾條規則（哪幾條會被測到）
4. Codex review 時對照本檔逐條檢視；若 Claude 沒遵守，直接列為 finding
