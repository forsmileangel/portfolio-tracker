# Portfolio Tracker 持倉追蹤

台股、美股、港股的個人持倉管理工具，不需要安裝任何 app，用瀏覽器開啟就能用，也可以加到手機主畫面像 app 一樣操作。

## 線上使用

👉 https://forsmileangel.github.io/portfolio-tracker/portfolio-tracker-v15.html

## 主要功能

- 📊 持倉管理：買入、賣出、自動計算加權平均成本
- 💹 即時報價：透過 Yahoo Finance 或 Google Sheet 更新股價
- 💱 幣別切換：USD / TWD，支援即時匯率
- 📈 基本面：PE、FPE、PEG、EPS 等指標
- 🔬 技術面：KD、MACD、RSI（時 / 日 / 週）
- 📰 個股新聞：近 7 天相關新聞
- 🌐 總體經濟：S&P500、VIX、美債、美元指數等
- 📁 CSV 匯入 / 匯出

## 手機安裝（Android）

1. 用 Chrome 開啟上方連結
2. 右上角 ⋮ → **安裝應用程式**
3. 桌面會出現「持倉追蹤」圖示，點開即用

## 持倉保留說明

匯入持倉後，每筆持倉旁邊有一個勾選框：

- ✅ 打勾 → 關閉後下次開啟仍在
- ☐ 不打勾 → 關閉後消失

標題列有「全選」勾選框可以一次全選。

> 注意：持倉資料存在瀏覽器本機，**不會跨裝置同步**。手機和電腦需分別設定。

## 股價更新方式

**方式一：一鍵更新（需設定 Google Sheet）**
在底部填入 Google Sheet CSV 連結，點「一鍵更新報價 + 匯率」自動抓取。

**方式二：手動輸入**
點「手動輸入報價」，逐一填入最新股價。

## 本機開發

需要基本面資料（PE、EPS 等）時，需啟動後端：

```bash
pip install yfinance
python server.py
```

啟動後開啟 `http://localhost:3000/portfolio-tracker-v15.html`

## 版本說明

| 版本 | 說明 |
|------|------|
| v15 | 目前版本，藍黑色系，持倉保留勾選 |
| v13 | 舊版，保留備用 |

## 技術

純 HTML + CSS + JavaScript，無框架，單一檔案。
