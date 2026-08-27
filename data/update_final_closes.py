#!/usr/bin/env python3
"""Build a small, date-exact final-close dataset for the Portfolio Tracker.

The file is deliberately independent from fundamentals.json.  A transient
failure keeps the previous bars, and a missing date is never replaced by an
older date.  The script is safe to run from GitHub Actions or locally with
--dry-run.
"""
from __future__ import annotations

import argparse
import html as html_lib
import json
import math
import re
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

try:
    import requests
except ImportError:  # pragma: no cover - GitHub Actions installs requests via yfinance
    requests = None

try:
    import yfinance as yf
except ImportError:  # pragma: no cover - only needed by the US updater
    yf = None


ROOT = Path(__file__).resolve().parent.parent
SYMBOLS_PATH = ROOT / "data" / "symbols.json"
FUNDAMENTALS_PATH = ROOT / "data" / "fundamentals.json"
OUTPUT_PATH = ROOT / "data" / "final-closes.json"

MARKET_TZ = {
    "TW": ZoneInfo("Asia/Taipei"),
    "HK": ZoneInfo("Asia/Hong_Kong"),
    "US": ZoneInfo("America/New_York"),
}
MARKET_CLOSE_MIN = {"TW": 13 * 60 + 30, "HK": 16 * 60 + 10, "US": 16 * 60}
PSEUDO_SYMBOLS = {"USD", "TWD", "HKD", "CASH", "BTC", "ETH", "ADA", "BNB", "SUI", "SOL"}
SOURCE_RANK = {
    "fundamentals-bootstrap": 10,
    "yahoo-yfinance-final": 20,
    "twse-stock-day": 30,
    "hkex-daily-quotation": 30,
}
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
NUMBER_RE = re.compile(r"[-+]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?")


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def safe_price(value) -> float | None:
    try:
        value = str(value).replace(",", "").strip()
        if not value or value in {"-", "--", "N/A", "null"}:
            return None
        number = float(value)
        return round(number, 8) if math.isfinite(number) and number > 0 else None
    except (TypeError, ValueError):
        return None


def load_json(path: Path, default):
    try:
        with path.open("r", encoding="utf-8") as handle:
            value = json.load(handle)
        return value
    except (OSError, ValueError, TypeError):
        return default


def symbol_market(symbol: str, hk_codes: set[str]) -> str | None:
    value = str(symbol or "").strip().upper()
    if not value or value in PSEUDO_SYMBOLS or value.endswith("-USD"):
        return None
    if value.endswith(".KS"):
        return None
    if value.endswith(".HK"):
        return "HK"
    if value.endswith(".TW") or value.endswith(".TWO"):
        return "TW"
    if re.fullmatch(r"\d{4}", value) and value in hk_codes:
        return "HK"
    if re.fullmatch(r"\d{4,6}[A-Z]?", value):
        return "TW"
    return "US"


def canonical_symbol(symbol: str, market: str, hk_codes: set[str]) -> str:
    value = str(symbol or "").strip().upper()
    if market == "HK":
        base = value[:-3] if value.endswith(".HK") else value
        return base.zfill(4) + ".HK"
    if market == "TW":
        if value.endswith(".TW") or value.endswith(".TWO"):
            return value
        return value + ".TW"
    return value


def tracked_symbols() -> tuple[dict[str, set[str]], set[str]]:
    raw_symbols = load_json(SYMBOLS_PATH, [])
    if not isinstance(raw_symbols, list):
        raw_symbols = []
    hk_codes = {
        str(item).strip().upper()[:-3].zfill(4)
        for item in raw_symbols
        if isinstance(item, str) and item.strip().upper().endswith(".HK")
    }
    result = {"TW": set(), "HK": set(), "US": set()}
    for raw in raw_symbols:
        market = symbol_market(raw, hk_codes)
        if market:
            result[market].add(canonical_symbol(raw, market, hk_codes))
    return result, hk_codes


def empty_payload() -> dict:
    return {"version": 1, "generatedAt": None, "symbols": {}, "markets": {}}


def normalize_payload(value) -> dict:
    source = value if isinstance(value, dict) else {}
    output = empty_payload()
    output["version"] = 1
    output["generatedAt"] = source.get("generatedAt") if isinstance(source.get("generatedAt"), str) else None
    output["markets"] = source.get("markets") if isinstance(source.get("markets"), dict) else {}
    symbols = source.get("symbols") if isinstance(source.get("symbols"), dict) else {}
    for symbol, slot in symbols.items():
        if not isinstance(slot, dict):
            continue
        by_date = slot.get("byDate") if isinstance(slot.get("byDate"), dict) else {}
        clean_dates = {}
        for day, bar in by_date.items():
            if not DATE_RE.fullmatch(str(day)) or not isinstance(bar, dict):
                continue
            close = safe_price(bar.get("close"))
            if close is None:
                continue
            clean_dates[str(day)] = {
                "close": close,
                "final": bar.get("final") is True,
                "source": str(bar.get("source") or "unknown"),
                "fetchedAt": bar.get("fetchedAt") if isinstance(bar.get("fetchedAt"), str) else None,
            }
        if clean_dates:
            output["symbols"][str(symbol).upper()] = {
                "market": str(slot.get("market") or "").upper(),
                "byDate": clean_dates,
            }
    return output


def source_rank(source: str) -> int:
    for name, rank in SOURCE_RANK.items():
        if source == name or source.startswith(name + ":"):
            return rank
    return 0


def merge_bar(payload: dict, symbol: str, market: str, day: str, close, source: str, fetched_at: str) -> bool:
    value = safe_price(close)
    if value is None or not DATE_RE.fullmatch(str(day)):
        return False
    symbols = payload.setdefault("symbols", {})
    slot = symbols.setdefault(symbol, {"market": market, "byDate": {}})
    slot["market"] = market
    by_date = slot.setdefault("byDate", {})
    old = by_date.get(day)
    new = {"close": value, "final": True, "source": source, "fetchedAt": fetched_at}
    if isinstance(old, dict):
        old_rank = source_rank(str(old.get("source") or ""))
        new_rank = source_rank(source)
        if new_rank < old_rank:
            return False
        if old.get("close") == value and old.get("source") == source and old.get("final") is True:
            return False
    by_date[day] = new
    return True


def completed_latest_day(market: str, now: datetime | None = None) -> date:
    local_now = (now or datetime.now(timezone.utc)).astimezone(MARKET_TZ[market])
    minutes = local_now.hour * 60 + local_now.minute
    current = local_now.date()
    if minutes < MARKET_CLOSE_MIN[market] + 5:
        current -= timedelta(days=1)
    return current


def recent_weekdays(latest: date, limit: int = 10) -> list[date]:
    days = []
    cursor = latest
    while len(days) < limit:
        if cursor.weekday() < 5:
            days.append(cursor)
        cursor -= timedelta(days=1)
    return days


def http_text(url: str, timeout: int = 35) -> tuple[int, str]:
    headers = {"User-Agent": "PortfolioTracker-final-close/15.957 (+https://github.com/forsmileangel/portfolio-tracker)"}
    if requests is not None:
        response = requests.get(url, headers=headers, timeout=timeout)
        return response.status_code, response.content.decode(response.encoding or "utf-8", errors="replace")
    from urllib.request import Request, urlopen
    request = Request(url, headers=headers)
    with urlopen(request, timeout=timeout) as response:  # nosec B310 - fixed public sources
        return response.status, response.read().decode("utf-8", errors="replace")


def clean_report_text(value: str) -> str:
    value = re.sub(r"<br\s*/?>", "\n", value, flags=re.IGNORECASE)
    value = re.sub(r"<[^>]+>", "", value)
    value = html_lib.unescape(value).replace("\xa0", " ")
    return value


def parse_hkex_daily_quotation(value: str, codes: set[str]) -> dict[str, float]:
    text = clean_report_text(value)
    lines = text.splitlines()
    # The same report repeats stock codes in market highlights, sales records,
    # and order-book sections. Restrict parsing to the formal QUOTATIONS table.
    start = next((i for i, line in enumerate(lines)
                  if line.strip().upper() == "QUOTATIONS"
                  and any("PRV.CLO" in lines[j].upper() for j in range(i + 1, min(i + 5, len(lines))))), 0)
    end = next((i for i in range(start + 1, len(lines))
                if lines[i].strip().upper() == "SALES RECORDS FOR ALL STOCKS"), len(lines))
    lines = lines[start:end]
    result = {}
    wanted = {str(code).zfill(4) for code in codes}
    for index, line in enumerate(lines):
        match = re.match(r"^\s*\*?\s*(\d{4})(?:\s|$)", line)
        if not match or match.group(1) not in wanted:
            continue
        continuation = ""
        for next_line in lines[index + 1:index + 4]:
            if next_line.strip():
                continuation = next_line
                break
        numbers = NUMBER_RE.findall(continuation)
        close = safe_price(numbers[0]) if numbers else None
        if close is not None:
            result[match.group(1)] = close
    return result


def fetch_hk(payload: dict, symbols: set[str], reports: dict, dry_run: bool) -> int:
    codes = {symbol[:-3] for symbol in symbols if symbol.endswith(".HK")}
    if not codes:
        reports["HK"] = {"status": "skipped", "source": "hkex-daily-quotation"}
        return 0
    latest = completed_latest_day("HK")
    candidates = recent_weekdays(latest, 10)
    # Always re-check the latest four report days. HKEX can publish a revised
    # page after the first run, and this also repairs a stale parser result.
    pages_needed = candidates[:4]

    fetched_dates = 0
    updated = 0
    errors = 0
    checked_at = now_utc_iso()
    for day in pages_needed:
        url = f"https://www.hkex.com.hk/eng/stat/smstat/dayquot/d{day:%y%m%de}.htm"
        try:
            status, body = http_text(url)
            if status == 404:
                continue
            if status < 200 or status >= 300:
                raise RuntimeError(f"HTTP {status}")
            rows = parse_hkex_daily_quotation(body, codes)
            if not rows:
                raise RuntimeError("target rows not found")
            fetched_dates += 1
            for code, close in rows.items():
                symbol = code + ".HK"
                if symbol in symbols:
                    updated += int(merge_bar(payload, symbol, "HK", day.isoformat(), close, "hkex-daily-quotation", checked_at))
        except Exception as exc:  # keep the last known bars on any one-page failure
            errors += 1
            print(f"HK {day}: {exc}", file=sys.stderr)
    reports["HK"] = {
        "status": "ok" if fetched_dates or not pages_needed else "partial",
        "source": "hkex-daily-quotation",
        "dates": fetched_dates,
        "errors": errors,
    }
    return updated


def parse_twse_rows(value: dict) -> list[tuple[str, float]]:
    rows = value.get("data") if isinstance(value, dict) else None
    if not isinstance(rows, list):
        return []
    output = []
    for row in rows:
        if not isinstance(row, list) or len(row) < 7:
            continue
        date_text = str(row[0]).strip()
        parts = date_text.split("/")
        if len(parts) != 3:
            continue
        try:
            day = date(int(parts[0]) + 1911, int(parts[1]), int(parts[2])).isoformat()
        except ValueError:
            continue
        close = safe_price(row[6])
        if close is not None:
            output.append((day, close))
    return output


def fetch_tw(payload: dict, symbols: set[str], reports: dict, dry_run: bool) -> int:
    codes = {symbol.rsplit(".", 1)[0] for symbol in symbols if symbol.endswith((".TW", ".TWO"))}
    if not codes:
        reports["TW"] = {"status": "skipped", "source": "twse-stock-day"}
        return 0
    local_now = datetime.now(timezone.utc).astimezone(MARKET_TZ["TW"])
    months = [(local_now.year, local_now.month)]
    previous = (local_now.replace(day=1) - timedelta(days=1))
    months.append((previous.year, previous.month))
    updated = 0
    successes = 0
    errors = 0
    checked_at = now_utc_iso()
    for code in sorted(codes):
        code_success = False
        for year, month in months:
            url = f"https://www.twse.com.tw/exchangeReport/STOCK_DAY?response=json&date={year:04d}{month:02d}01&stockNo={code}"
            try:
                status, body = http_text(url)
                if status < 200 or status >= 300:
                    raise RuntimeError(f"HTTP {status}")
                rows = parse_twse_rows(json.loads(body))
                if rows:
                    code_success = True
                for day, close in rows:
                    for suffix in (".TW", ".TWO"):
                        symbol = code + suffix
                        if symbol in symbols:
                            updated += int(merge_bar(payload, symbol, "TW", day, close, "twse-stock-day", checked_at))
            except Exception as exc:
                errors += 1
                print(f"TW {code} {year}-{month:02d}: {exc}", file=sys.stderr)
        successes += int(code_success)
    reports["TW"] = {
        "status": "ok" if successes == len(codes) else ("partial" if successes else "error"),
        "source": "twse-stock-day",
        "symbols": successes,
        "total": len(codes),
        "errors": errors,
    }
    return updated


def history_date(index_value, market_tz: ZoneInfo) -> date:
    timestamp = index_value
    if hasattr(timestamp, "tz_convert") and getattr(timestamp, "tzinfo", None) is not None:
        timestamp = timestamp.tz_convert(market_tz)
    elif hasattr(timestamp, "tz_localize") and getattr(timestamp, "tzinfo", None) is None:
        timestamp = timestamp.tz_localize(market_tz)
    return timestamp.date() if hasattr(timestamp, "date") else date.fromisoformat(str(timestamp)[:10])


def fetch_us(payload: dict, symbols: set[str], reports: dict, dry_run: bool) -> int:
    if yf is None:
        reports["US"] = {"status": "error", "source": "yahoo-yfinance-final", "error": "yfinance unavailable"}
        return 0
    local_now = datetime.now(timezone.utc).astimezone(MARKET_TZ["US"])
    today = local_now.date()
    after_close = local_now.hour * 60 + local_now.minute >= MARKET_CLOSE_MIN["US"] + 5
    updated = 0
    successes = 0
    errors = 0
    checked_at = now_utc_iso()
    for symbol in sorted(symbols):
        try:
            history = yf.Ticker(symbol).history(period="45d", interval="1d", auto_adjust=False, actions=False)
            if history is None or history.empty or "Close" not in history.columns:
                continue
            got_bar = False
            for index_value, row in history.iterrows():
                day = history_date(index_value, MARKET_TZ["US"])
                if day > today or (day == today and not after_close):
                    continue
                close = row.get("Close")
                if close is None:
                    continue
                updated += int(merge_bar(payload, symbol, "US", day.isoformat(), close, "yahoo-yfinance-final", checked_at))
                got_bar = safe_price(close) is not None or got_bar
            successes += int(got_bar)
        except Exception as exc:
            errors += 1
            print(f"US {symbol}: {exc}", file=sys.stderr)
        time.sleep(0.15)
    reports["US"] = {
        "status": "ok" if successes == len(symbols) else ("partial" if successes else "error"),
        "source": "yahoo-yfinance-final",
        "symbols": successes,
        "total": len(symbols),
        "errors": errors,
    }
    return updated


def bootstrap_from_fundamentals(payload: dict, market_symbols: dict[str, set[str]], hk_codes: set[str]) -> int:
    fundamentals = load_json(FUNDAMENTALS_PATH, {})
    data = fundamentals.get("data") if isinstance(fundamentals, dict) else None
    if not isinstance(data, dict):
        return 0
    updated = 0
    fetched_at = fundamentals.get("generated") if isinstance(fundamentals.get("generated"), str) else now_utc_iso()
    for raw_symbol, entry in data.items():
        market = symbol_market(raw_symbol, hk_codes)
        if not market:
            continue
        symbol = canonical_symbol(raw_symbol, market, hk_codes)
        if symbol not in market_symbols[market] or not isinstance(entry, dict):
            continue
        closes = entry.get("recent_closes")
        if not isinstance(closes, list):
            continue
        for bar in closes:
            if not isinstance(bar, dict):
                continue
            day = str(bar.get("date") or "")
            if DATE_RE.fullmatch(day):
                updated += int(merge_bar(payload, symbol, market, day, bar.get("close"), "fundamentals-bootstrap", fetched_at))
    return updated


def prune_payload(payload: dict, limit: int = 30) -> None:
    for slot in payload.get("symbols", {}).values():
        by_date = slot.get("byDate", {}) if isinstance(slot, dict) else {}
        if isinstance(by_date, dict) and len(by_date) > limit:
            keep = sorted(by_date)[-limit:]
            slot["byDate"] = {day: by_date[day] for day in keep}


def symbols_snapshot(payload: dict) -> str:
    return json.dumps(payload.get("symbols", {}), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def write_payload(payload: dict) -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def run(target_market: str, dry_run: bool = False) -> int:
    market_symbols, hk_codes = tracked_symbols()
    payload = normalize_payload(load_json(OUTPUT_PATH, {}))
    before = symbols_snapshot(payload)
    bootstrap_from_fundamentals(payload, market_symbols, hk_codes)
    reports = {}
    if target_market in {"ALL", "TW"}:
        fetch_tw(payload, market_symbols["TW"], reports, dry_run)
    if target_market in {"ALL", "HK"}:
        fetch_hk(payload, market_symbols["HK"], reports, dry_run)
    if target_market in {"ALL", "US"}:
        fetch_us(payload, market_symbols["US"], reports, dry_run)
    prune_payload(payload)
    after = symbols_snapshot(payload)
    changed = before != after
    if changed or not OUTPUT_PATH.exists():
        payload["generatedAt"] = now_utc_iso()
    payload["markets"] = reports
    if (changed or not OUTPUT_PATH.exists()) and not dry_run:
        write_payload(payload)
    print(json.dumps({"changed": changed, "dryRun": dry_run, "reports": reports}, ensure_ascii=False))
    if dry_run and changed:
        print(f"dry-run: {len(payload.get('symbols', {}))} symbols contain final-close bars")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--market", choices=("ALL", "TW", "HK", "US"), default="ALL")
    parser.add_argument("--dry-run", action="store_true", help="fetch and validate without writing final-closes.json")
    args = parser.parse_args()
    return run(args.market, args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
