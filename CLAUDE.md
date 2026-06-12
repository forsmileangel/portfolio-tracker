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
| v15.9（目前，v15.924）| 投資日（台北 08:00 換日）損益模型、close pair 單一來源（final 驗證）；v15.900 為凍結基準（git tag，可回退） |
| v15.0xx | v15.900 之前系列：藍黑色系、持倉保留勾選、Service Worker 自動更新 |
| v13 | 舊版，保留備用，勿刪 |

## 操作守則
1. 只改 `portfolio-tracker-v15.html`，除非明確指定其他檔案
2. 每次修改後更新頂端 `<!-- 更新日誌 -->` 的版本號
3. 輸出檔名固定為 `portfolio-tracker-v15.html`
4. 不主動新增功能，等使用者說要什麼再做
5. 進行前端設計或 UI 調整時，參考 `.claude/skills/frontend-design/SKILL.md`

## 版本號規則（fallback 後直接續編，不跳號）

當使用者 fallback / rollback / 退回到某版本後，**下一次進版直接從那版 +1 開始**，不需要避開「曾經出現過但已被覆蓋」的版本號。

**範例**：
- 退回到 `v15.900` → 下次進版是 `v15.901`（即使先前已有過 v15.901/902/903/904）
- 退回到 `v15.901` → 下次進版是 `v15.902`
- 退回到 `v15.082` → 下次進版是 `v15.083`

**邏輯**：fallback 表示使用者放棄那版之後的所有改動。新的同號版本（例如新的 v15.901）直接覆蓋舊版意義，git 歷史保留即可。

**例外**：使用者明確說「保留 vX.Y 不可重用」才特別標記跳號；否則**不要主動建議跳號**（如 v15.903、v15.905 這種「跳過 abandoned」的命名是錯的，過去做過幾次反而造成混亂）。

**Claude 行為**：使用者要求進版時，直接用「目前 APP_VERSION + 1」當作新版本號，不需問也不需查 git history 比對。

## 架構規則
詳細規則已模組化至 `.claude/rules/`：
- `sync-invariants.md`：**改 Gist / FSA / 快照 / pending / hash / PWA 啟動流程前必讀的同步不變式**（v15.069-v15.079 踩過的坑全在這）
- `rendering.md`：差異更新架構（不可改回 innerHTML 全部重建）
- `performance.md`：效能規則（防抖、onchange）
- `gist-sync.md`：新增欄位時的同步 checklist + Gist API 錯誤處理（401/403、e.status、_isAuthError）
- `notion.md`：Notion 寫作規則與頁面 ID
- `storage-keys.md`：localStorage key 必須登記至 `STORAGE_KEYS` 物件，rename 需有 migration
- `cache-strategy.md`：對外資料須有時間戳顯色、stale fallback、新增基本面欄位 5 步 checklist

**硬性規則**：改 Gist 同步、FSA 本地同步、daily/market snapshot、dirty domain / pending count、userDataHash、PWA 啟動流程**任一**前，必須先讀 `sync-invariants.md` 與 `gist-sync.md`，並對照修改前 Checklist 8 條逐項回答 yes/no。不可只看當前需求埋頭改。

**規則例外**：規則不是 100% 強制。當當前需求與規則衝突時，**不得自行打破**，必須在 plan / 回應中明確列出：(a) 違反哪一條規則、(b) 可能重現哪個已修補回歸點或產生何種同步異常、(c) 是否有替代方案，交由使用者明確同意後才動 code，並在 `sync-invariants.md` §11 留例外日誌。詳見 `sync-invariants.md` §0。

**規則進化**：同一節規則被破例累計第 2 次需主動提醒、**第 3 次禁止再以例外處理**，必須提出新規則文字交由使用者決定是否升級規則本身（規則應與實際需求同步進化，不可當神主牌）。

## Git 設定
- Auto-commit hook 已設定：修改檔案後自動 `git add → commit → push`
- 不需要手動 commit，Claude Code 每次存檔會自動觸發
