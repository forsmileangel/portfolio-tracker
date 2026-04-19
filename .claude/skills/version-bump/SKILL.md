---
name: version-bump
description: Portfolio Tracker 進版流程。當使用者確認要進版時自動引導完整步驟，確保 HTML 更新日誌、Notion 紀錄同步更新。
---

## 觸發時機
- 使用者說「進版」「更新版本」「寫版本紀錄」時
- 完成一組功能修改後使用者確認要發布時

## 執行步驟

1. **確認版本號**：讀取 `portfolio-tracker-v15.html` 頂端 `<!-- 更新日誌 -->` 取得目前版本號，遞增一位
2. **撰寫摘要**：根據本次修改內容，用中文撰寫版本摘要（參考 Notion 版本紀錄的既有格式）
3. **更新 HTML**：在 `<!-- 更新日誌 -->` 區塊頂部加入新版本號與日期
4. **更新 Notion**：在版本更新紀錄頁面（`33efec73b1638158b992ffe9706be0be`）頂部新增對應段落
5. **Push**：確認修改已 push 到 GitHub

## 格式規範
- 版本號：`v15.XXX`（三位數遞增）
- Notion 段落格式：`### v15.XXX — YYYY-MM-DD` + 粗體副標題 + 條列式說明
- Notion 標題不放 emoji，用 icon 欄位設定圖示
