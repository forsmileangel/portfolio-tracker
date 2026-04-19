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

## 操作守則
1. 只改 `portfolio-tracker-v15.html`，除非明確指定其他檔案
2. 每次修改後更新頂端 `<!-- 更新日誌 -->` 的版本號
3. 輸出檔名固定為 `portfolio-tracker-v15.html`
4. 不主動新增功能，等使用者說要什麼再做
5. 進行前端設計或 UI 調整時，參考 `.claude/skills/frontend-design/SKILL.md`

## 架構規則
詳細規則已模組化至 `.claude/rules/`：
- `rendering.md`：差異更新架構（不可改回 innerHTML 全部重建）
- `performance.md`：效能規則（防抖、onchange）
- `gist-sync.md`：新增欄位時的同步 checklist
- `notion.md`：Notion 寫作規則與頁面 ID

## Git 設定
- Auto-commit hook 已設定：修改檔案後自動 `git add → commit → push`
- 不需要手動 commit，Claude Code 每次存檔會自動觸發
