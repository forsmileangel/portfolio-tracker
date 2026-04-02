# CLAUDE.md

## 專案定位
單一 HTML 檔案的股票持倉追蹤器，部署在 GitHub Pages，以 PWA 形式安裝在 Android 手機使用。

## 關鍵資訊
- **Repo**：https://github.com/Forsmileangel/portfolio-tracker
- **線上網址**：https://forsmileangel.github.io/portfolio-tracker/portfolio-tracker-v15.html
- **主程式**：`portfolio-tracker-v15.html`（所有邏輯都在這一個檔案裡）
- **Storage Key**：`pt_v13p_state`（localStorage）

## 技術
純 HTML / CSS / JS，無框架。Chart.js 4.4.1。Yahoo Finance API（CORS proxy）。

## v15 相較 v13 的差異
- 持倉保留勾選（`persist` 欄位，只有 `persist: true` 才存入 localStorage）
- 全選 checkbox（`#persist-all-checkbox`，支援 indeterminate）
- 預設空白持倉（`IMPORT_DATA = { "holdings": [] }`）
- 藍黑色系（主色 `#60a5fa` / `#2563eb`，取代原本 `#fbbf24`）
- Service Worker 自動偵測新版並更新

## 版本日誌
```
v15.0 - 基於 v13，持倉保留勾選，預設空白持倉
v15.1 - 配色藍黑色系
v15.2 - Service Worker 自動更新
```

## 操作守則
1. 只改 `portfolio-tracker-v15.html`，除非明確指定其他檔案
2. 每次修改後更新頂端 `<!-- 更新日誌 -->` 的版本號
3. 輸出檔名固定為 `portfolio-tracker-v15.html`
4. 使用者用平板操作，回答簡潔
5. 不主動新增功能，等使用者說要什麼再做

## 開新對話時
- 只討論：上傳此 `CLAUDE.md` 即可
- 需修改程式碼：上傳 `CLAUDE.md` + `portfolio-tracker-v15.html`
- 不需要上傳整個 ZIP
