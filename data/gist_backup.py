"""
Portfolio Tracker — Gist → SQLite 每日備份腳本

用途：從 GitHub Gist 拉取最新的 Portfolio Tracker 資料，
      寫入本地 SQLite 資料庫 (data/portfolio_backup.db)。

使用方式：
    python data/gist_backup.py

環境變數：
    GIST_TOKEN  — GitHub Personal Access Token（需 gist scope）
    GIST_ID     — 儲存 Portfolio Tracker 資料的 Gist ID
"""

import json
import os
import sqlite3
import sys
from datetime import datetime
from urllib.request import Request, urlopen
from urllib.error import HTTPError

# ── 設定 ──
GIST_TOKEN = os.environ.get('GIST_TOKEN', '')
GIST_ID = os.environ.get('GIST_ID', '')
GIST_FILENAME = 'portfolio-tracker-holdings.json'
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'portfolio_backup.db')


def fetch_gist():
    """從 GitHub Gist API 取得 JSON 資料"""
    if not GIST_TOKEN or not GIST_ID:
        print('❌ 缺少 GIST_TOKEN 或 GIST_ID 環境變數')
        sys.exit(1)

    url = f'https://api.github.com/gists/{GIST_ID}'
    req = Request(url, headers={
        'Authorization': f'token {GIST_TOKEN}',
        'Accept': 'application/vnd.github.v3+json',
    })
    try:
        with urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
    except HTTPError as e:
        print(f'❌ Gist API 錯誤：HTTP {e.code}')
        sys.exit(1)

    raw_url = data.get('files', {}).get(GIST_FILENAME, {}).get('raw_url')
    if not raw_url:
        print(f'❌ 找不到 {GIST_FILENAME}')
        sys.exit(1)

    req2 = Request(raw_url)
    with urlopen(req2, timeout=30) as resp:
        return json.loads(resp.read().decode())


def init_db(conn):
    """建立所有 table（若尚未存在）"""
    c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS snapshots (
        date TEXT PRIMARY KEY,
        stock_twd REAL NOT NULL
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS holdings (
        sync_date TEXT NOT NULL,
        symbol TEXT NOT NULL,
        market TEXT,
        name TEXT,
        quantity REAL,
        cost_price REAL,
        current_price REAL,
        added_date TEXT,
        lots_json TEXT,
        PRIMARY KEY (sync_date, symbol)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS trade_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        symbol TEXT NOT NULL,
        market TEXT,
        qty REAL,
        price REAL,
        date TEXT,
        realized_pl REAL,
        lots_consumed_json TEXT,
        UNIQUE(symbol, date, qty, price)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS deposits (
        sync_date TEXT NOT NULL,
        bank TEXT,
        currency TEXT,
        amount REAL,
        note TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS watchlist (
        sync_date TEXT NOT NULL,
        symbol TEXT NOT NULL,
        market TEXT,
        PRIMARY KEY (sync_date, symbol)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS settings (
        sync_date TEXT PRIMARY KEY,
        currency TEXT,
        usd_twd REAL,
        hkd_twd REAL,
        extra_rates_json TEXT,
        crypto_twd REAL,
        crypto_pie_cb INTEGER,
        moxa_twd REAL,
        moxa_pie_cb INTEGER,
        cash_pie_cb INTEGER,
        sheet_url TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS sync_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sync_time TEXT NOT NULL,
        pushed_at TEXT,
        holdings_count INTEGER,
        snapshots_count INTEGER,
        trades_count INTEGER,
        deposits_count INTEGER,
        raw_json TEXT
    )''')

    conn.commit()


def upsert_data(conn, data):
    """將 Gist JSON 資料寫入 SQLite"""
    c = conn.cursor()
    today = datetime.utcnow().strftime('%Y-%m-%d')

    # ── snapshots（累積，不覆蓋）──
    for s in data.get('marketSnapshots', []):
        c.execute(
            'INSERT OR REPLACE INTO snapshots (date, stock_twd) VALUES (?, ?)',
            (s.get('date'), s.get('stockTWD', 0))
        )

    # ── holdings（每日快照，同日覆蓋）──
    c.execute('DELETE FROM holdings WHERE sync_date = ?', (today,))
    for h in data.get('holdings', []):
        c.execute(
            '''INSERT INTO holdings
               (sync_date, symbol, market, name, quantity, cost_price, current_price, added_date, lots_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (today, h.get('symbol'), h.get('market'), h.get('name'),
             h.get('quantity'), h.get('costPrice'), h.get('currentPrice'),
             h.get('addedDate'), json.dumps(h.get('lots', []), ensure_ascii=False))
        )

    # ── trade_history（累積，去重）──
    for t in data.get('tradeHistory', []):
        c.execute(
            '''INSERT OR IGNORE INTO trade_history
               (symbol, market, qty, price, date, realized_pl, lots_consumed_json)
               VALUES (?, ?, ?, ?, ?, ?, ?)''',
            (t.get('symbol'), t.get('market'), t.get('qty'), t.get('price'),
             t.get('date'), t.get('realizedPL'),
             json.dumps(t.get('lotsConsumed', []), ensure_ascii=False))
        )

    # ── deposits（每日快照，同日覆蓋）──
    c.execute('DELETE FROM deposits WHERE sync_date = ?', (today,))
    for d in data.get('deposits', []):
        c.execute(
            '''INSERT INTO deposits (sync_date, bank, currency, amount, note)
               VALUES (?, ?, ?, ?, ?)''',
            (today, d.get('bank'), d.get('currency'), d.get('amount'), d.get('note'))
        )

    # ── watchlist（每日快照，同日覆蓋）──
    c.execute('DELETE FROM watchlist WHERE sync_date = ?', (today,))
    for w in data.get('watchlist', []):
        c.execute(
            'INSERT INTO watchlist (sync_date, symbol, market) VALUES (?, ?, ?)',
            (today, w.get('symbol'), w.get('market'))
        )

    # ── settings（每日快照）──
    ex = data.get('exchangeRates', {})
    c.execute(
        '''INSERT OR REPLACE INTO settings
           (sync_date, currency, usd_twd, hkd_twd, extra_rates_json,
            crypto_twd, crypto_pie_cb, moxa_twd, moxa_pie_cb, cash_pie_cb, sheet_url)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
        (today, data.get('currency'), ex.get('USD_TWD'), ex.get('HKD_TWD'),
         json.dumps(ex.get('extra', {}), ensure_ascii=False),
         data.get('crypto_twd', 0), int(data.get('crypto_pie_cb', False)),
         data.get('moxa_twd', 0), int(data.get('moxa_pie_cb', False)),
         int(data.get('cash_pie_cb', False)), data.get('sheet_url', ''))
    )

    # ── sync_log（每次執行記一筆）──
    c.execute(
        '''INSERT INTO sync_log
           (sync_time, pushed_at, holdings_count, snapshots_count, trades_count, deposits_count, raw_json)
           VALUES (?, ?, ?, ?, ?, ?, ?)''',
        (datetime.utcnow().isoformat() + 'Z',
         data.get('pushedAt'),
         len(data.get('holdings', [])),
         len(data.get('marketSnapshots', [])),
         len(data.get('tradeHistory', [])),
         len(data.get('deposits', [])),
         json.dumps(data, ensure_ascii=False))
    )

    conn.commit()


def main():
    print(f'📦 Portfolio Tracker Gist → SQLite 備份')
    print(f'   DB: {DB_PATH}')
    print()

    # 1. 從 Gist 拉取
    print('⏳ 從 Gist 拉取資料...')
    data = fetch_gist()
    pushed_at = data.get('pushedAt', '未知')
    print(f'✅ 拉取成功（上次推送：{pushed_at}）')

    # 2. 寫入 SQLite
    print('⏳ 寫入 SQLite...')
    conn = sqlite3.connect(DB_PATH)
    try:
        init_db(conn)
        upsert_data(conn, data)
    finally:
        conn.close()

    # 3. 摘要
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    snap_count = c.execute('SELECT COUNT(*) FROM snapshots').fetchone()[0]
    hold_count = c.execute('SELECT COUNT(DISTINCT symbol) FROM holdings').fetchone()[0]
    trade_count = c.execute('SELECT COUNT(*) FROM trade_history').fetchone()[0]
    dep_count = c.execute('SELECT COUNT(*) FROM deposits WHERE sync_date = ?',
                          (datetime.utcnow().strftime('%Y-%m-%d'),)).fetchone()[0]
    sync_count = c.execute('SELECT COUNT(*) FROM sync_log').fetchone()[0]
    conn.close()

    print()
    print(f'✅ 備份完成！摘要：')
    print(f'   快照：{snap_count} 筆')
    print(f'   持倉：{hold_count} 檔')
    print(f'   交易：{trade_count} 筆')
    print(f'   存款：{dep_count} 筆')
    print(f'   同步紀錄：{sync_count} 次')


if __name__ == '__main__':
    main()
