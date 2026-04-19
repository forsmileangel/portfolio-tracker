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
