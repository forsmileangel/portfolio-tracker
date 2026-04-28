# localStorage Key 管理規則（v15.063 起）

## 集中登記原則

所有 localStorage key 必須集中登記在 `portfolio-tracker-v15.html` 中的 `STORAGE_KEYS` 物件內。

新增任何 localStorage key 之前：

1. 先到 `STORAGE_KEYS` 加上一條登記，**包括分組註解**（主要狀態 / UI 偏好 / Gist 同步 / 快取 / 後端 等）
2. 程式碼中引用時可選擇 `STORAGE_KEYS.xxx` 或既有的 `PT_XXX_KEY` 常數，但**不得使用未登記的字串字面值**
3. PR / commit 訊息明寫新增了哪個 key、為什麼

## Key 字串值不可隨意 rename

舊的 key 一旦 ship 出去就會在使用者瀏覽器 / 手機 PWA 的 localStorage 留下資料。隨意 rename 會：

- 使用者下次開啟看不到原本的設定（資料還在但讀不到）
- Gist 同步可能寫入空值蓋掉雲端
- 跨裝置出現「我這邊有但那邊沒有」的詭異現象

若**真的必須 rename**：

1. 設計 migration：開頁時讀舊 key、寫到新 key、刪舊 key
2. 設計 rollback 路徑：若新版有問題回滾到舊版時，新 key 寫的內容能否被舊版讀（通常不能 → 這是不可逆變更，需謹慎）
3. 寫一個版本標記避免 migration 跑兩次（例如 `pt_migrated_v2 = '1'`）
4. 至少在三個裝置（電腦 / 手機 PWA / 隱私視窗模擬新使用者）測過

## 不允許的反模式

- ❌ `localStorage.setItem('something_new', value)` — 散落字串字面值
- ❌ 把 PT_XXX_KEY 改成 `pt_xxx_v2`（rename 不算 migration，會丟資料）
- ❌ 在 update_fund.py / restore_from_sqlite.py 等後端程式中硬寫 key（後端不該碰使用者 localStorage）

## 已棄用 key 的處理

`STORAGE_KEYS.cashLegacy = 'pt_v13_cash'` 這種已棄用 key**保留登記**，目的：

- 文件化「這個 key 還可能存在於老使用者的 localStorage 中」
- 未來若要正式清除，先寫 migration 再刪登記

## 為何採用「保守版」（v15.063）

v15.063 把 `STORAGE_KEYS` 物件加進來但**沒有強迫替換既有 PT_XXX_KEY 常數**，理由：

- 替換 30 個常數定義的風險高（typo 會讓常數變 undefined）
- 集中登記的主要價值是「未來新增 / rename 時有單一查找點」
- 既有程式碼仍能正常運作

**未來方向**（不在 v15.063 範圍）：

- 想把 `PT_XXX_KEY = STORAGE_KEYS.xxx` 改造完成是 OK 的，但需逐個替換並 grep 驗證
- 散落的字串字面值（`localStorage.getItem('font_size')` 等）也可以漸進式換成 `STORAGE_KEYS.fontSize`
