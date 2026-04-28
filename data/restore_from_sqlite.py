"""
從 portfolio_backup.db 還原指定備份的 Gist payload JSON

來源：sync_log 表的 raw_json 欄位（每次 GitHub Actions 跑 gist_backup.py 時寫入）。
**直接用 raw_json 不重組**——避免漏掉新欄位（schema_version、sync_meta、earnings_proxy_symbol 等）。

本工具只會輸出檔案，不會：
  - 覆蓋 Gist
  - 修改任何前端 localStorage
  - 改任何雲端服務狀態

下一步要還原時，請人工檢查輸出 JSON 內容無誤，再從 Portfolio Tracker → 設定 → Gist 區塊手動推送。

用法：
    python data/restore_from_sqlite.py --list
    python data/restore_from_sqlite.py --latest --out restore.json
    python data/restore_from_sqlite.py --id 8 --out restore.json
    python data/restore_from_sqlite.py --date 2026-04-25 --out restore.json
    python data/restore_from_sqlite.py --db /custom/path/portfolio_backup.db --list
"""
import argparse
import json
import os
import sqlite3
import sys


DEFAULT_DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'portfolio_backup.db')


def cmd_list(conn, limit=20):
    cur = conn.cursor()
    cur.execute(
        'SELECT id, sync_time, pushed_at, holdings_count, deposits_count, '
        'trades_count, snapshots_count FROM sync_log ORDER BY id DESC LIMIT ?',
        (limit,)
    )
    rows = cur.fetchall()
    if not rows:
        print('sync_log 表為空——尚未跑過任何 Gist 備份。')
        return

    # 對齊欄寬
    headers = ['id', 'sync_time', 'pushed_at', 'holdings', 'deposits', 'trades', 'snapshots']
    widths = [4, 27, 27, 9, 9, 7, 10]
    line = '  '.join(h.ljust(w) for h, w in zip(headers, widths))
    print(line)
    print('  '.join('-' * w for w in widths))
    for r in rows:
        cells = [
            str(r[0]).ljust(widths[0]),
            (r[1] or '').ljust(widths[1]),
            (r[2] or '').ljust(widths[2]),
            str(r[3] if r[3] is not None else '-').ljust(widths[3]),
            str(r[4] if r[4] is not None else '-').ljust(widths[4]),
            str(r[5] if r[5] is not None else '-').ljust(widths[5]),
            str(r[6] if r[6] is not None else '-').ljust(widths[6]),
        ]
        print('  '.join(cells))
    print(f'\n共 {len(rows)} 筆（最多顯示 {limit} 筆）。要看更舊紀錄請加 --limit N。')


def fetch_raw_json(conn, where_clause, params):
    cur = conn.cursor()
    cur.execute(
        f'SELECT id, sync_time, pushed_at, raw_json FROM sync_log '
        f'WHERE {where_clause} ORDER BY id DESC LIMIT 1',
        params
    )
    row = cur.fetchone()
    if not row:
        return None
    return {
        'id': row[0],
        'sync_time': row[1],
        'pushed_at': row[2],
        'raw_json': row[3],
    }


def write_output(record, out_path):
    if not record:
        print('找不到符合條件的備份。請先執行 --list 確認可用的備份。', file=sys.stderr)
        sys.exit(1)
    if not record['raw_json']:
        print(f'備份 id={record["id"]} 的 raw_json 為空（可能是早期版本未保存原始 JSON）。', file=sys.stderr)
        sys.exit(1)

    # 確認可以解析（驗證資料完整性）
    try:
        parsed = json.loads(record['raw_json'])
    except json.JSONDecodeError as e:
        print(f'備份 id={record["id"]} 的 raw_json 無法解析：{e}', file=sys.stderr)
        sys.exit(1)

    if os.path.exists(out_path):
        print(f'警告：{out_path} 已存在，將覆寫。')

    with open(out_path, 'w', encoding='utf-8') as f:
        # 重新序列化（縮排好讀），不直接寫入字串以避免 BOM 等差異
        json.dump(parsed, f, ensure_ascii=False, indent=2)

    keys = list(parsed.keys())[:8]
    print(f'\n已匯出備份：')
    print(f'  id            : {record["id"]}')
    print(f'  sync_time     : {record["sync_time"]}')
    print(f'  pushed_at     : {record["pushed_at"]}')
    print(f'  輸出檔案      : {out_path}')
    print(f'  payload size  : {len(record["raw_json"])} bytes')
    print(f'  top-level keys: {keys}{" ..." if len(parsed) > len(keys) else ""}')
    print()
    print('下一步：人工檢視內容無誤後，至 Portfolio Tracker → 設定 → Gist 區塊')
    print('      ① 確認 Gist Token 有效')
    print('      ② 用「拉取」備份目前雲端狀態（避免誤刪）')
    print('      ③ 將本檔案內容貼回去後手動「推送」')


def main():
    parser = argparse.ArgumentParser(
        description='從 portfolio_backup.db 還原指定備份的 Gist payload',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument('--db', default=DEFAULT_DB, help=f'SQLite 路徑（預設：{DEFAULT_DB}）')
    parser.add_argument('--out', help='輸出 JSON 檔案路徑（搭配 --latest / --id / --date 使用）')

    sel = parser.add_mutually_exclusive_group()
    sel.add_argument('--list', action='store_true', help='列出最近的備份紀錄')
    sel.add_argument('--latest', action='store_true', help='匯出最新一筆備份')
    sel.add_argument('--id', type=int, help='匯出指定 sync_log id 的備份')
    sel.add_argument('--date', help='匯出指定日期（YYYY-MM-DD）當日最新一筆備份')

    parser.add_argument('--limit', type=int, default=20, help='--list 顯示筆數（預設 20）')

    args = parser.parse_args()

    if not os.path.exists(args.db):
        print(f'找不到資料庫：{args.db}', file=sys.stderr)
        print('提示：portfolio_backup.db 由 GitHub Actions 每天 04:30（台灣時間）自動產生。', file=sys.stderr)
        print('請先 git pull 取得最新備份，或用 --db 指定其他路徑。', file=sys.stderr)
        sys.exit(1)

    if not (args.list or args.latest or args.id is not None or args.date):
        parser.print_help()
        sys.exit(0)

    conn = sqlite3.connect(args.db)
    try:
        if args.list:
            cmd_list(conn, limit=args.limit)
            return

        if not args.out:
            print('--latest / --id / --date 必須搭配 --out FILE 使用', file=sys.stderr)
            sys.exit(2)

        if args.latest:
            record = fetch_raw_json(conn, '1=1', ())
        elif args.id is not None:
            record = fetch_raw_json(conn, 'id = ?', (args.id,))
        elif args.date:
            # 比對 pushed_at 或 sync_time 是否以該日期開頭
            record = fetch_raw_json(
                conn,
                "(pushed_at LIKE ? OR sync_time LIKE ?)",
                (f'{args.date}%', f'{args.date}%')
            )
        else:
            record = None

        write_output(record, args.out)
    finally:
        conn.close()


if __name__ == '__main__':
    main()
