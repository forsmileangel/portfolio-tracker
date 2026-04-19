檢查 GitHub Actions 最近的執行狀態。

檢查項目：
1. **Update Fundamentals Data**：基本面更新（每 6 小時）
2. **Backup Gist to SQLite**：Gist 備份（每天台灣 04:30）

對每個 workflow 報告：
- 最近 3 次執行的成功/失敗狀態
- 如果有失敗，查看錯誤 log 並摘要原因
- 建議修復方式

使用 `gh run list` 和 `gh run view` 指令。若 gh CLI 不可用，提供 GitHub Actions 頁面連結讓使用者手動查看。
