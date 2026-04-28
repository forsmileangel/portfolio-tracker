## Gist 同步 — 新增欄位 Checklist

若要新增同類型手動輸入欄位（TWD 值 + 圓餅圖勾選），需同步修改以下 7 處：

1. **HTML**：輸入列（`width:90px` 固定標籤寬度對齊）
2. **總資產列**：`ta-xxx-wrap` + `ta-xxx` span
3. **`renderPie()`**：讀取值、計算 grandTotal、勾選框顏色、pie slice、pieColors
4. **localStorage**：`PT_XXX_KEY` + `PT_XXX_PIE_KEY` 常數
5. **`saveXxx()` / `loadXxx()`**：對應讀寫函式
6. **`gistPush()`**：payload 加入 `xxx_twd` / `xxx_pie_cb`
7. **`gistPull()`**：還原區塊
8. **啟動初始化**：`loadXxx()` 呼叫

---

## Gist 讀取規則（v15.051 起）

拉取 Gist 檔案內容時，**優先用 API response 內嵌的 `content`，不要走 `raw_url`**。

### 原因
- `api.github.com` 回傳的 `content` 欄位是**即時**的，反映剛 push 的最新內容
- `raw_url`（`gist.githubusercontent.com`）走 Fastly CDN，會快取數分鐘到數十分鐘
- `cache: 'no-store'` 只能繞過瀏覽器快取，**繞不過 CDN 快取**
- 先前 bug：push 完馬上 pull，`raw_url` 拿到舊版資料 → 本地資料被舊值覆蓋

### 標準寫法

```javascript
const res = await fetch(`https://api.github.com/gists/${gistId}`, {
    headers: { 'Authorization': `token ${token}`, 'Accept': 'application/vnd.github.v3+json' },
    cache: 'no-store'
});
const data = await res.json();
const gistFile = data.files?.[GIST_FILENAME];

let saved;
if (gistFile.content && !gistFile.truncated) {
    saved = JSON.parse(gistFile.content);         // ✅ 優先：內嵌 content
} else {
    // fallback：檔案 > 1MB 被 API truncated 時才用 raw_url
    const fileRes = await fetch(gistFile.raw_url, { cache: 'no-store' });
    saved = await fileRes.json();
}
```

### 通用原則（適用其他服務）

只要 API 同時提供「inline 內容」與「CDN 檔案網址」兩種讀取路徑，且需要**寫入後立即讀最新值**，一律用 inline：

| 服務 | 用這個 | 別用這個 |
|------|--------|---------|
| GitHub Gist API | `files[x].content` | `raw_url` |
| GitHub Contents API | `content`（base64 解碼） | `download_url` |
| S3 + CloudFront | S3 直接讀 | CloudFront URL |

任何 `*.githubusercontent.com`、`cdn.*`、CloudFront 類 URL 都帶 CDN 快取，除非能接受分鐘級延遲，否則不要當主路徑。

---

## Gist API 錯誤處理規則（v15.061 / v15.062 起）

### 必須保留 HTTP status

任何呼叫 Gist API 的 fetch 失敗時，throw 的 Error 必須附帶 `e.status = res.status`，**不能只靠 message**。

理由：GitHub Gist API 401 回的 response body 是 `{"message": "Bad credentials"}`，原本 `throw new Error(err.message || HTTP ${res.status})` 會優先使用 `err.message` → Error.message 變成 "Bad credentials" → 不含 "HTTP 401" → 用 message regex 抓不到。

### 標準寫法

```javascript
if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    const e = new Error(err.message || `HTTP ${res.status}`);
    e.status = res.status;   // 保留 HTTP status 給 _isAuthError / _recordPushError
    throw e;
}
```

### Auth 判斷必須看 status 與關鍵字

```javascript
function _isAuthError(err) {
    if (err?.status === 401 || err?.status === 403) return true;
    const msg = (err?.message || '').toLowerCase();
    if (msg.includes('bad credentials')) return true;
    if (msg.includes('requires authentication')) return true;
    if (msg.includes('must authenticate')) return true;
    const m = msg.match(/http\s+(\d+)/);
    if (!m) return false;
    const code = parseInt(m[1], 10);
    return code === 401 || code === 403;
}
```

### 401/403 必須立即停止 retry

當判定為 auth error 時：

```javascript
function _handleAuthFailure() {
    _pushRetryCount = MAX_PUSH_RETRY;     // 強制停止 retry 計數
    clearTimeout(_retryTimer);
    showWarnToast('❌ Gist Token 失效或權限不足，請至設定重新填入 Token', 8000);
}
```

**不可**繼續 `_scheduleRetry()`，5 次重試對 Token 失效完全無意義。

### 所有 push 路徑都要記錄錯誤

`_gistSilentPush()` 與手動 `gistPush()` 的 catch 區塊都必須：

1. 呼叫 `_recordPushError(e)` 寫 `pt_last_push_error` localStorage
2. 用 `_isAuthError(e)` 判斷是否 auth 失敗
3. 若是 → `_handleAuthFailure()`；若否 → 顯示一般錯誤 toast
4. 推送成功時記得 `localStorage.removeItem('pt_last_push_error')` 清除

### Preflight 也要做這套處理

`gistPush()` 的 preflight 區塊（`_preflightGistPush()` throw 時的 catch）也必須跑同樣流程。v15.061 漏了這段，由 v15.062 補上。
