# Portfolio Tracker — CLAUDE.md

## 專案定位
台股、美股、港股的個人持倉追蹤器。
單一 HTML 檔案，部署在 GitHub Pages，以 PWA 安裝在 Android 手機使用。

## 關鍵資訊
- **Repo**：https://github.com/forsmileangel/portfolio-tracker
- **線上網址**：https://forsmileangel.github.io/portfolio-tracker/portfolio-tracker-v15.html
- **主程式**：`portfolio-tracker-v15.html`（所有邏輯都在這一個檔案裡）
- **Storage Key**：`pt_v13p_state`（localStorage）

## 技術
純 HTML / CSS / JS，無框架。Chart.js 4.4.1。Yahoo Finance API（CORS proxy）。

## 後端（本機開發用）
- `server.py`：提供 CORS proxy 與基本面資料（PE、FPE、PEG、EPS）
- 啟動：`python server.py`，開啟 `http://localhost:3000/portfolio-tracker-v15.html`
- 部署在 Render（`Procfile` 定義）

## 版本現況
| 版本 | 說明 |
|------|------|
| v15（目前）| 藍黑色系、持倉保留勾選、Service Worker 自動更新 |
| v13 | 舊版，保留備用，勿刪 |

### v15 相較 v13 的主要差異
- 持倉保留勾選（`persist` 欄位，只有 `persist: true` 才存入 localStorage）
- 全選 checkbox（`#persist-all-checkbox`，支援 indeterminate）
- 預設空白持倉（`IMPORT_DATA = { "holdings": [] }`）
- 藍黑色系（主色 `#60a5fa` / `#2563eb`）
- Service Worker 自動偵測新版並更新

## 操作守則
1. 只改 `portfolio-tracker-v15.html`，除非明確指定其他檔案
2. 每次修改後更新頂端 `<!-- 更新日誌 -->` 的版本號
3. 輸出檔名固定為 `portfolio-tracker-v15.html`
4. 不主動新增功能，等使用者說要什麼再做
5. 進行前端設計或 UI 調整時，參考 `SKILL_frontend-design.md` 的設計原則

## 渲染架構：差異更新（v15.022 起）

`renderHoldingsDetail()` 採差異更新，**不要改回 `innerHTML` 全部重建**。

### 模式說明
- 每張持倉卡片有 `id="hcard-${h.id}"` 
- `_cardCache = {}` 儲存 `{ [h.id]: fingerprint }`
- `_cardExpanded = {}` 儲存每張卡片目前的展開/收合狀態
- `_cardFingerprint(h)` 將所有顯示欄位壓成一個字串（含 `currency`）
- `_buildCardHTML(h, i, isExpanded)` 產生單張卡片的 HTML 字串

### 更新邏輯
1. 先掃描已不存在的 id → `el.remove()` + 清除快取
2. 依排序順序遍歷每個 holding：
   - 卡片不存在 → 建立並用 `insertBefore` 插入正確位置
   - 卡片存在但 fingerprint 不同 → 讀取目前展開狀態後用 `replaceWith` 替換
   - 卡片存在且 fingerprint 相同 → 只確認 DOM 順序，不動內容
3. `toggleHolding(id)` 直接操作 DOM，不需 render；同時更新 `_cardExpanded[id]`

### 新增類似欄位（cash/crypto/moxa 模式）
若要新增同類型手動輸入欄位（TWD 值 + 圓餅圖勾選），需同步修改：
1. **HTML**：輸入列（`width:90px` 固定標籤寬度對齊）
2. **總資產列**：`ta-xxx-wrap` + `ta-xxx` span
3. **`renderPie()`**：讀取值、計算 grandTotal、勾選框顏色、pie slice、pieColors
4. **localStorage**：`PT_XXX_KEY` + `PT_XXX_PIE_KEY` 常數
5. **`saveXxx()` / `loadXxx()`**：對應讀寫函式
6. **`gistPush()`**：payload 加入 `xxx_twd` / `xxx_pie_cb`
7. **`gistPull()`**：還原區塊
8. **啟動初始化**：`loadXxx()` 呼叫

### 效能規則（v15.022）
- 現金/加密/MOXA 輸入框用 `onchange`（不用 `oninput`）
- `saveToStorage()` 只能透過 `_debouncedSave` 在 renderAll 內呼叫（500ms 防抖）
- 直接 DOM 操作（toggleHolding、_renderFxTable）不呼叫 renderAll

## Notion 寫作規則
- 建立或更新 Notion 頁面時，**不在標題文字裡放 emoji**
- 改用 Notion 頁面的 `icon` 欄位設定圖示（API `icon` 參數）
- 目的：避免圖示重複顯示（sidebar 同時顯示 icon 欄位 + 標題內 emoji）

## Git 設定
- Auto-commit hook 已設定：修改檔案後自動 `git add → commit → push`
- 不需要手動 commit，Claude Code 每次存檔會自動觸發
