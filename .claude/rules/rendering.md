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
