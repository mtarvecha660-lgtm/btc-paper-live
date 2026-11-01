"""Liquidation-fair returns (backtest + live dashboard) and live-tick failure handling."""
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

from btcpaper.backtest import run_range
from btcpaper.metrics import liquidation_value, summarize, trade_stats
from tests.helpers import cfg, synthetic

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "live"))


class LiquidationIsFair(unittest.TestCase):
    def test_open_position_is_counted_as_sold(self):
        """A strategy still holding BTC at the end is valued as if sold at the last close with fee + slippage."""
        c = cfg()
        df = synthetic(400, seed=7, step_ms=3_600_000)
        sig = df.copy()
        sig["enter"] = False
        sig.loc[10, "enter"] = True               # buy once, never sell
        sig["exit"] = False
        sig["stop"] = sig["close"] * 0.5          # far stop: never hit
        sig["note"] = ""
        m, trades, equity, _ = run_range(None, sig, c, 0, len(df), "1h")
        self.assertTrue(m["open_position"])
        buy = [t for t in trades if t["side"] == "BUY"][0]
        cash = c["starting_balance_usdt"] - buy["value"] - buy["fee"]
        expected = liquidation_value(cash, buy["qty"], df["close"].iloc[-1], c["fee_pct"], c["slippage_pct"])
        self.assertAlmostEqual(m["end_equity"], expected, places=6)
        self.assertAlmostEqual(m["return_pct"], (expected / c["starting_balance_usdt"] - 1) * 100, places=9)
        self.assertLess(m["end_equity"], m["end_equity_mark_to_market"])   # selling costs something
        self.assertAlmostEqual(m["excess_vs_hold_pct"], m["return_pct"] - m["hold_return_pct"], places=9)

    def test_same_position_same_rule_as_hold(self):
        """Holding exactly the hold-benchmark's BTC gives exactly the hold-benchmark's return."""
        closes = list(60000 * np.exp(np.cumsum(np.r_[0, np.random.default_rng(1).normal(0, 0.01, 99)])))
        start, fee, slip = 10000.0, 0.1, 0.05
        hold_qty = start / (1 + fee / 100) / (closes[0] * (1 + slip / 100))
        equity = [hold_qty * c for c in closes]
        m = summarize(equity, [], "1h", start, closes, fee, slip, end_cash=0.0, end_qty=hold_qty)
        self.assertAlmostEqual(m["return_pct"], m["hold_return_pct"], places=9)
        self.assertAlmostEqual(m["excess_vs_hold_pct"], 0.0, places=9)

    def test_trade_stats(self):
        trades = [
            {"trade_id": 1, "side": "BUY", "pnl": None, "fee": 1.0},
            {"trade_id": 1, "side": "SELL", "pnl": 18.0, "fee": 1.0},   # gross +20
            {"trade_id": 2, "side": "BUY", "pnl": None, "fee": 1.0},
            {"trade_id": 2, "side": "SELL", "pnl": -12.0, "fee": 1.0},  # gross -10
        ]
        s = trade_stats(trades)
        self.assertEqual(s["trades"], 2)
        self.assertAlmostEqual(s["profit_factor"], 18 / 12)
        self.assertAlmostEqual(s["expectancy_usdt"], 3.0)
        self.assertAlmostEqual(s["avg_win_usdt"], 18.0)
        self.assertAlmostEqual(s["avg_loss_usdt"], -12.0)
        self.assertAlmostEqual(s["gross_pnl_usdt"], 10.0)
        self.assertAlmostEqual(s["fees_pct_of_gross"], 40.0)

    def test_dashboard_uses_liquidation_value(self):
        import build_site
        with tempfile.TemporaryDirectory() as tmp:
            live = Path(tmp)
            (live / "state" / "a").mkdir(parents=True)
            (live / "accounts.json").write_text(json.dumps({"timeframe": "1h", "start_inr": 1000, "accounts": [
                {"id": "a", "label": "A", "strategy": "ema_cross", "params": {}}]}))
            (live / "meta.json").write_text(json.dumps({"start_usdt": 1000, "inr_per_usdt_at_start": 1,
                                                         "fee_pct": 0.1, "slippage_pct": 0.05}))
            eng = {"cash": 500.0, "qty": 0.01, "start_balance": 1000.0, "entry_price": 50000, "stop": 40000,
                   "fees_paid": 0.5, "realized_pnl": 0.0, "last_close": 50000, "pending": None, "halted_day": None}
            (live / "state" / "a" / "state.json").write_text(json.dumps({"engine": eng, "params": {}}))
            with mock.patch.object(build_site, "LIVE", live), mock.patch.object(build_site, "STATE", live / "state"):
                out = build_site.build_latest(price=50000.0)
            a = out["accounts"][0]
            self.assertAlmostEqual(a["equity_usdt"], liquidation_value(500, 0.01, 50000, 0.1, 0.05))
            self.assertLess(a["equity_usdt"], 500 + 0.01 * 50000)


class TickFailuresAreLoud(unittest.TestCase):
    def setUp(self):
        import build_site
        import tick
        self.tick, self.bs = tick, build_site
        self.tmp = Path(tempfile.mkdtemp())
        shutil.copy(ROOT / "live" / "accounts.json", self.tmp / "accounts.json")
        self.patches = [
            mock.patch.object(tick, "LIVE", self.tmp), mock.patch.object(tick, "STATE", self.tmp / "state"),
            mock.patch.object(tick, "TICKS", self.tmp / "ticks.csv"),
            mock.patch.object(build_site, "LIVE", self.tmp), mock.patch.object(build_site, "STATE", self.tmp / "state"),
            mock.patch.object(tick.D, "usdt_inr", lambda *_a, **_k: (90.0, "test")),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _latest(self):
        return json.loads((self.tmp / "latest.json").read_text())

    def test_data_outage_exits_nonzero_and_is_logged(self):
        def boom(*_a, **_k):
            raise self.tick.D.DataError("HTTP 503: simulated outage")
        with mock.patch.dict(self.tick.D.FETCHERS, {k: boom for k in self.tick.D.FETCHERS}):
            rc = self.tick.main()
        self.assertNotEqual(rc, 0)
        rows = (self.tmp / "ticks.csv").read_text().strip().splitlines()
        self.assertIn(",skipped,", rows[-1])
        h = self._latest()["health"]
        self.assertEqual(h["consecutive_failures"], 1)
        self.assertIsNone(h["last_ok_tick_utc"])
        self.assertTrue(h["stale"])

    def test_one_broken_account_fails_the_run_but_others_still_run(self):
        ran = []

        def fake_run(acc, cfg_, tf, start):
            ran.append(acc["id"])
            if acc["id"] == "ema_cross":
                raise RuntimeError("strategy blew up")
            return True, ""
        with mock.patch.object(self.tick.D, "last_price", lambda *_a, **_k: (100000.0, "test")), \
                mock.patch.object(self.tick, "run_strategy", fake_run):
            rc = self.tick.main()
        self.assertNotEqual(rc, 0)
        self.assertEqual(ran, ["ema_cross", "rsi_meanrev", "donchian_breakout"])
        self.assertTrue((self.tmp / "state" / "hold_btc" / "state.json").exists())   # benchmark still bought
        last = (self.tmp / "ticks.csv").read_text().strip().splitlines()[-1]
        self.assertIn(",error,", last)
        self.assertIn("ema_cross", last)

    def test_health_counts_failures_in_a_row(self):
        ticks = [{"time_utc": "2026-11-01 09:00:00", "status": "ok"},
                 {"time_utc": "2026-11-01 09:15:00", "status": "skipped"},
                 {"time_utc": "2026-11-01 09:30:00", "status": "error"}]
        from datetime import datetime, timezone
        h = self.bs.health(ticks, now=datetime(2026, 11, 1, 10, 0, tzinfo=timezone.utc))
        self.assertEqual(h["consecutive_failures"], 2)
        self.assertEqual(h["last_ok_tick_utc"], "2026-11-01 09:00:00")
        self.assertAlmostEqual(h["minutes_since_ok"], 60.0)
        self.assertTrue(h["stale"])                       # 60 min > 45 min
        h2 = self.bs.health(ticks[:1], now=datetime(2026, 11, 1, 9, 20, tzinfo=timezone.utc))
        self.assertFalse(h2["stale"])


if __name__ == "__main__":
    unittest.main()
