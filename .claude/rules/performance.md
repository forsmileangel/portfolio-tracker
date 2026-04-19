## 效能規則（v15.022 起）

- 現金/加密/MOXA 輸入框用 `onchange`（不用 `oninput`）
- `saveToStorage()` 只能透過 `_debouncedSave` 在 renderAll 內呼叫（500ms 防抖）
- 直接 DOM 操作（toggleHolding、_renderFxTable）不呼叫 renderAll
