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
