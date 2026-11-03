#!/usr/bin/env python3
"""Trigger the "Update Final Close Data" workflow right after each market closes.

GitHub delays this repo's scheduled workflows by 3-10 hours (measured 2026-10-22
to 2026-11-02), so the official close file lands long after the close.  A
workflow_dispatch run starts within a minute.  This script is idempotent: a
market is dispatched only when it has a completed trading day that
data/final-closes.json on main does not yet cover, so the Windows task can run
it at several fixed Taipei times and let the market time zones decide.

Usage: python scripts/trigger_final_closes.py [--dry-run] [--now ISO] [--markets TW,HK,US]
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from data import update_final_closes as closes  # noqa: E402  (yfinance / requests are optional there)

REPO = "forsmileangel/portfolio-tracker"
WORKFLOW = "update-final-closes.yml"
LOG_PATH = ROOT / "scripts" / "final_close_trigger_log.txt"
MARKETS = ("TW", "HK", "US")


def market_calendar(market: str) -> tuple[set[str], dict[str, int]]:
    """Holidays and early closes for one market, read from the app's MARKET_CALENDARS."""
    app = (ROOT / "portfolio-tracker-v15.html").read_text(encoding="utf-8")
    tz = closes.MARKET_TZ[market].key
    block = re.search(r"\b" + market + r":\s*\{\s*tz:\s*'" + re.escape(tz) + r"'(.*?)\n\s*\}(?=,\s*\n\s*(?:TW|HK|US):|\s*\};)", app, re.S)
    if not block:
        raise ValueError(f"{market} market calendar not found in app")
    body = re.sub(r"//[^\n]*", "", block[1])
    holidays_match = re.search(r"holidays:\s*new Set\(\[(.*?)\]\)", body, re.S)
    holidays = set(re.findall(r"'([0-9]{4}-[0-9]{2}-[0-9]{2})'", holidays_match[1])) if holidays_match else set()
    early_match = re.search(r"earlyClose:\s*\{(.*?)\}", body, re.S)
    early = {day: int(hour) * 60 for day, hour in re.findall(r"'([0-9-]+)':\s*(\d+)\s*\*\s*60", early_match[1])} if early_match else {}
    return holidays, early


def completed_trading_day(market: str, now: datetime) -> tuple[date, str]:
    """Latest trading day whose close + settle buffer has passed, and a short reason."""
    holidays, early = market_calendar(market)
    local_now = now.astimezone(closes.MARKET_TZ[market])
    day = local_now.date()
    close_min = early.get(day.isoformat(), closes.MARKET_CLOSE_MIN[market])
    settled = local_now.hour * 60 + local_now.minute >= close_min + closes.MARKET_SETTLE_BUFFER_MIN[market]
    reason = f"local {local_now:%Y-%m-%d %H:%M} {'settled' if settled else 'not yet settled'}"
    if not settled:
        day -= timedelta(days=1)
    while day.weekday() >= 5 or day.isoformat() in holidays:
        day -= timedelta(days=1)
    return day, reason


def gh(*args: str) -> str:
    result = subprocess.run(["gh", *args], capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout or f"gh exit {result.returncode}").strip()[:300])
    return result.stdout


def official_payload() -> dict:
    raw = gh("api", f"repos/{REPO}/contents/data/final-closes.json?ref=main", "-H", "Accept: application/vnd.github.raw+json")
    return closes.normalize_payload(json.loads(raw))


def is_official(bar) -> bool:
    return isinstance(bar, dict) and bar.get("final") is True and closes.source_rank(bar.get("source", "")) >= 20


def missing_symbols(payload: dict, symbols: set[str], day: date) -> list[str]:
    """Tracked symbols without an official bar for `day`.

    A symbol with no official bar at all in the last 14 days (delisted, e.g. 9747.HK
    after the counter migration) is ignored, otherwise it would re-dispatch forever.
    """
    floor = (day - timedelta(days=14)).isoformat()
    out = []
    for symbol in sorted(symbols):
        by_date = payload.get("symbols", {}).get(symbol, {}).get("byDate", {})
        if is_official(by_date.get(day.isoformat())):
            continue
        if any(is_official(bar) for d, bar in by_date.items() if d >= floor):
            out.append(symbol)
    return out


def log(line: str) -> None:
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(line)
    try:
        with LOG_PATH.open("a", encoding="utf-8") as handle:
            handle.write(f"[{stamp}] {line}\n")
    except OSError:
        pass


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="decide only; do not dispatch")
    parser.add_argument("--now", help="ISO time to evaluate instead of the current time (e.g. 2026-11-03T05:40+08:00)")
    parser.add_argument("--markets", default=",".join(MARKETS))
    args = parser.parse_args()
    now = datetime.fromisoformat(args.now) if args.now else datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=ZoneInfo("Asia/Taipei"))

    market_symbols, _ = closes.tracked_symbols()
    try:
        payload = official_payload()
    except Exception as exc:
        log(f"ERROR reading official file: {exc}")
        return 1

    failures = 0
    for market in [m.strip().upper() for m in args.markets.split(",") if m.strip()]:
        symbols = market_symbols.get(market) or set()
        if not symbols:
            log(f"{market}: no tracked symbols, skip")
            continue
        day, reason = completed_trading_day(market, now)
        missing = missing_symbols(payload, symbols, day)
        if not missing:
            log(f"{market}: {day} complete in official file ({reason}), skip")
            continue
        note = f"{market}: {day} missing {len(missing)}/{len(symbols)} ({reason})"
        if args.dry_run:
            log(note + ", dry-run: would dispatch")
            continue
        try:
            gh("workflow", "run", WORKFLOW, "-R", REPO, "-f", f"market={market}")
            log(note + ", dispatched")
        except Exception as exc:
            failures += 1
            log(note + f", dispatch FAILED: {exc}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
