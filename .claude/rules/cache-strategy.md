# 快取策略規則

## 對外資料必須有時間戳顯示

任何來自外部 API / GitHub Actions 產出 / CDN 的資料，前端顯示時必須讓使用者看得出資料新鮮度。

實作參照（v15.063 起）：

```javascript
// helper：依資料年齡決定顯示色
function _freshnessColor(ageMs, freshMaxMs, staleMs) {
    if (ageMs == null || isNaN(ageMs)) return '#7e93a6';
    if (ageMs <= freshMaxMs) return '#7e93a6';   // 灰藍：新鮮
    if (ageMs <= staleMs)    return '#fbbf24';   // 橘：接近過期
    return '#ef4444';                            // 紅：已過期
}
```

呼叫時三個參數：`ageMs` 是當前 `Date.now() - 資料時間戳`，`freshMaxMs` 是新鮮上限，`staleMs` 是接近過期上限（超過此值視為已過期）。

## 各類資料的 TTL 與閾值建議

| 資料 | TTL | 新鮮（灰藍） | 接近過期（橘） | 已過期（紅） |
|------|-----|------------|-------------|-----------|
| 基本面（fundamentals.json） | 8hr | <6hr | 6–12hr | >12hr |
| 技術面（pf_analysis_v8.tech_ts） | 1hr | <45min | 45–90min | >90min |
| 匯率（pt_fx_v1.ts） | 1hr | <30min | 30–90min | >90min |

橘色 = 接近 TTL；紅色 = 超過 TTL 1.5 倍以上。

## 失敗時用 stale fallback，不要清成 `{}`

API / fetch 失敗時的處理原則：

- ✅ 保留上一次成功的快取資料（讓使用者看舊值總比看空白好）
- ✅ 失敗時設 cache 為 `null`，下次進來會重新嘗試
- ❌ 失敗時設 cache 為 `{}` — `{}` 是 truthy，會讓下次的 `if (!cache) refetch()` 不進入

v15.042 已修正過這個 bug（`fundamentals.json` 失敗時設 `null`）。

## TTL 變更需配合 cache key bump

如果改變了快取資料**結構**（新欄位、欄位 rename、結構整理），必須升 cache key 版本：

```javascript
const _CACHE_KEY = 'pf_analysis_v8';   // 從 v7 升到 v8
```

否則使用者瀏覽器中的舊版快取會被當作有效資料讀回，導致前端 undefined。

例：v15.060 加入 `next_earnings_date` / `no_earnings` / `earnings_proxy_symbol` 三個欄位 → 把 `_CACHE_KEY` 從 `pf_analysis_v7` 升到 `pf_analysis_v8`，舊使用者下次開頁會自動重抓。

## 新增基本面欄位 checklist

當在 `data/update_fund.py` 加入新基本面欄位時，必須同步：

1. **後端** `data/update_fund.py`：抓取邏輯 + 寫入 `result[sym]` dict
2. **前端解析** `fetchSymbolDataFromYahoo()`：line 4196-4205 附近的 `f.xxx ?? null` 區塊新增解析
3. **前端 return 物件**：line 4248-4260 與 line 4390-4400 兩處 return 都要包含新欄位
4. **table render**：例如 `buildXxxTd()` 與 row push 中加入 `<td>${d.xxx}</td>`
5. **如有結構變更**：升 `_CACHE_KEY` 版本（v_N → v_N+1）並在註解寫出原因
6. **新增欄位若有 mapping 邏輯**：嚴格限定作用範圍（參考 v15.060 的 EARNINGS_PROXY 設計：mapping 只用於財報日期欄位，不影響 PE/EPS/技術面）

## 不要快取使用者 localStorage 的東西到 Service Worker

Service Worker 只應該快取**靜態資源**：HTML shell、CSS、第三方 library（如 Chart.js）。

**禁止**用 Service Worker 快取：

- `fundamentals.json`（API 回應）
- `*.googleapis.com` / `query1.finance.yahoo.com` / Gist API（即時資料）
- Google Sheet CSV（報價）

v15.024 之後 Service Worker 改為 no-op，正是因為前面踩到 SW 快取 API 結果的雷。
