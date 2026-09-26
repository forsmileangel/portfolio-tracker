import json
import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from data import update_final_closes as closes


class History:
    columns = ["Close"]

    def __init__(self, rows):
        self.rows = rows
        self.empty = not rows

    def iterrows(self):
        return ((date.fromisoformat(day), {"Close": value}) for day, value in self.rows)


class FinalCloseTests(unittest.TestCase):
    def setUp(self):
        self.payload = closes.empty_payload()
        self.reports = {}
        self.dates = (date(2026, 9, 25), date(2026, 9, 24))

    def fetch(self, rows, fallback=(), symbols=("MSTR",)):
        ticker = SimpleNamespace(history=lambda **kwargs: History(rows))
        with patch.object(closes, "yf", SimpleNamespace(Ticker=lambda symbol: ticker)), \
             patch.object(closes, "expected_us_close_dates", return_value=self.dates), \
             patch.object(closes, "fetch_us_chart", return_value=fallback) as chart, \
             patch.object(closes.time, "sleep"):
            closes.fetch_us(self.payload, set(symbols), self.reports, False)
            return chart.call_count

    def test_required_dates_skip_weekend_holiday_and_year_boundary(self):
        for instant, expected in [
            ("2026-09-26T00:40:00+00:00", ("2026-09-25", "2026-09-24")),
            ("2026-09-07T22:00:00+00:00", ("2026-09-04", "2026-09-03")),
            ("2027-01-01T22:00:00+00:00", ("2026-12-31", "2026-12-30")),
            ("2027-12-27T14:00:00+00:00", ("2027-12-23", "2027-12-22")),
        ]:
            with self.subTest(instant=instant):
                actual = closes.expected_us_close_dates(datetime.fromisoformat(instant))
                self.assertEqual(tuple(d.isoformat() for d in actual), expected)

    def test_thirty_minute_settlement_buffer_and_early_close(self):
        for instant, latest in [
            ("2026-09-25T20:29:00+00:00", "2026-09-24"),
            ("2026-09-25T20:30:00+00:00", "2026-09-25"),
            ("2026-11-27T18:29:00+00:00", "2026-11-25"),
            ("2026-11-27T18:30:00+00:00", "2026-11-27"),
        ]:
            with self.subTest(instant=instant):
                self.assertEqual(closes.expected_us_close_dates(datetime.fromisoformat(instant))[0].isoformat(), latest)

    def test_stale_yfinance_uses_chart_to_fill_required_date(self):
        calls = self.fetch([("2026-09-24", 161.61)], [("2026-09-24", 161.61), ("2026-09-25", 158.61)])
        self.assertEqual(calls, 1)
        self.assertEqual(self.reports["US"]["status"], "ok")
        bar = self.payload["symbols"]["MSTR"]["byDate"]["2026-09-25"]
        self.assertEqual(bar["source"], "yahoo-chart-final")
        self.assertTrue(bar["final"])
        self.assertAlmostEqual(bar["close"] - 161.61, -3)

    def test_old_dates_alone_never_count_as_success(self):
        self.fetch([("2026-09-23", 162.20), ("2026-09-24", 161.61)])
        self.assertEqual(self.reports["US"]["status"], "error")
        self.assertEqual(self.reports["US"]["missingSymbols"], ["MSTR"])
        self.assertEqual(self.reports["US"]["symbols"], 0)
        self.assertIn("2026-09-24", self.payload["symbols"]["MSTR"]["byDate"])

    def test_missing_previous_date_cannot_jump_back_two_days(self):
        self.fetch([("2026-09-23", 162.20), ("2026-09-25", 158.61)])
        self.assertEqual(self.reports["US"]["status"], "error")
        self.assertEqual(self.reports["US"]["previousDate"], "2026-09-24")

    def test_complete_pair_avoids_fallback_and_rejects_unsettled_day(self):
        calls = self.fetch([("2026-09-24", 161.61), ("2026-09-25", 158.61), ("2026-09-28", 999)])
        self.assertEqual(calls, 0)
        self.assertNotIn("2026-09-28", self.payload["symbols"]["MSTR"]["byDate"])

    def test_bootstrap_and_invalid_closes_cannot_fill_missing_day(self):
        closes.merge_bar(self.payload, "MSTR", "US", "2026-09-25", 158.845, "fundamentals-bootstrap", "old")
        self.fetch([("2026-09-24", 161.61), ("2026-09-25", float("nan"))])
        self.assertEqual(self.reports["US"]["status"], "error")
        self.assertFalse(self.payload["symbols"]["MSTR"]["byDate"]["2026-09-25"]["final"])

    def test_chart_keeps_null_indexes_and_market_dates_aligned(self):
        days = ["2026-09-23", "2026-09-24", "2026-09-25", "2026-09-28"]
        stamps = [int(datetime.fromisoformat(day + "T13:30:00+00:00").timestamp()) for day in days]
        body = {"chart": {"result": [{"timestamp": stamps, "indicators": {"quote": [{"close": [10, None, 12, 999]}]}}]}}
        with patch.object(closes, "http_text", return_value=(200, json.dumps(body))):
            self.assertEqual(closes.fetch_us_chart("MSTR", self.dates[0]), [("2026-09-23", 10), ("2026-09-25", 12)])

    def test_yfinance_outage_still_allows_chart_recovery(self):
        with patch.object(closes, "yf", None), \
             patch.object(closes, "expected_us_close_dates", return_value=self.dates), \
             patch.object(closes, "fetch_us_chart", return_value=[("2026-09-24", 161.61), ("2026-09-25", 158.61)]), \
             patch.object(closes.time, "sleep"):
            closes.fetch_us(self.payload, {"MSTR"}, self.reports, False)
        self.assertEqual(self.reports["US"]["status"], "ok")

    def test_network_failure_retains_saved_prices_and_reports_partial(self):
        closes.merge_bar(self.payload, "MSTR", "US", "2026-09-24", 161.61, "yahoo-yfinance-final", "old")
        ticker = SimpleNamespace(history=lambda **kwargs: History([]))
        with patch.object(closes, "yf", SimpleNamespace(Ticker=lambda symbol: ticker)), \
             patch.object(closes, "expected_us_close_dates", return_value=self.dates), \
             patch.object(closes, "fetch_us_chart", side_effect=RuntimeError("offline")), \
             patch.object(closes.time, "sleep"):
            closes.fetch_us(self.payload, {"MSTR"}, self.reports, False)
        self.assertEqual(self.payload["symbols"]["MSTR"]["byDate"]["2026-09-24"]["close"], 161.61)
        self.assertEqual(self.reports["US"]["status"], "error")

    def test_run_persists_failure_report_keeps_other_markets_and_returns_failure(self):
        self.payload["generatedAt"] = "2026-09-24T22:00:00Z"
        self.payload["markets"]["TW"] = {"status": "ok"}
        def fail(payload, symbols, reports, dry_run):
            reports["US"] = {"status": "partial", "missingSymbols": ["MSTR"]}
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "final.json"
            output.write_text(json.dumps(self.payload), encoding="utf-8")
            with patch.object(closes, "OUTPUT_PATH", output), \
                 patch.object(closes, "tracked_symbols", return_value=({"US": {"MSTR"}}, set())), \
                 patch.object(closes, "bootstrap_from_fundamentals"), \
                 patch.object(closes, "fetch_us", side_effect=fail):
                self.assertEqual(closes.run("US"), 1)
                written = json.loads(output.read_text(encoding="utf-8"))
                self.assertEqual(written["markets"]["TW"], {"status": "ok"})
                self.assertEqual(written["markets"]["US"]["status"], "partial")
                self.assertEqual(written["generatedAt"], self.payload["generatedAt"])
                before = output.read_bytes()
                closes.run("US", dry_run=True)
                self.assertEqual(output.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
