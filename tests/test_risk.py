import unittest

from btcpaper.config import load_config
from btcpaper.engine import Engine
from btcpaper.backtest import run_range
from btcpaper.strategies import load_all
from tests.helpers import cfg, bar, NOSIG, synthetic

H = 3_600_000
T0 = 1_700_000_000_000 + 6 * H      # some hour; days are judged in Asia/Kolkata


class Risk(unittest.TestCase):
    def test_max_position_cap(self):
        e = Engine(cfg(max_position_pct=25, risk_per_trade_pct=100))
        n, why = e.size_order(10000, 10000, 100.0, 50.0)
        self.assertAlmostEqual(n, 2500)
        self.assertIn("max_position", why)

    def test_risk_per_trade_sizing(self):
        e = Engine(cfg(max_position_pct=100, risk_per_trade_pct=1))
        n, _ = e.size_order(10000, 10000, 100.0, 90.0)          # 10% stop -> 1% risk = 1,000 notional
        self.assertAlmostEqual(n, 1000)

    def test_no_stop_no_trade(self):
        e = Engine(cfg())
        _, dec = e.on_bar(bar(T0, 100.0), {**NOSIG, "enter": True, "stop": float("nan")})
        self.assertEqual(dec["action"], "SKIP")
        _, dec = e.on_bar(bar(T0 + H, 100.0), {**NOSIG, "enter": True, "stop": 105.0})   # stop above price
        self.assertEqual(dec["action"], "SKIP")
        self.assertEqual(e.s["qty"], 0)

    def test_stop_loss_and_gap_fill(self):
        e = Engine(cfg(slippage_pct=0))
        e.on_bar(bar(T0, 100.0), {**NOSIG, "enter": True, "stop": 95.0})
        e.on_bar(bar(T0 + H, 100.0), NOSIG)
        ev, _ = e.on_bar(bar(T0 + 2 * H, 99.0, h=99.5, l=94.0, c=96.0), NOSIG)   # low pierces 95
        self.assertEqual(ev[0]["side"], "SELL")
        self.assertAlmostEqual(ev[0]["price"], 95.0)
        e2 = Engine(cfg(slippage_pct=0))
        e2.on_bar(bar(T0, 100.0), {**NOSIG, "enter": True, "stop": 95.0})
        e2.on_bar(bar(T0 + H, 100.0), NOSIG)
        ev, _ = e2.on_bar(bar(T0 + 2 * H, 90.0, h=91, l=89, c=90.5), NOSIG)      # gapped below the stop
        self.assertAlmostEqual(ev[0]["price"], 90.0)                              # filled at the open, not 95

    def test_daily_loss_limit_halts_until_tomorrow(self):
        e = Engine(cfg(daily_loss_limit_pct=3, max_position_pct=100, risk_per_trade_pct=100, slippage_pct=0, fee_pct=0))
        e.on_bar(bar(T0, 100.0), {**NOSIG, "enter": True, "stop": 50.0})
        e.on_bar(bar(T0 + H, 100.0), NOSIG)                                       # long ~100% of equity
        _, dec = e.on_bar(bar(T0 + 2 * H, 100.0, l=95.0, c=96.0), NOSIG)           # -4% today
        self.assertEqual(dec["action"], "HALT")
        ev, _ = e.on_bar(bar(T0 + 3 * H, 96.0), {**NOSIG, "enter": True, "stop": 90.0})
        self.assertEqual(ev[0]["side"], "SELL")                                   # position closed at next open
        _, dec = e.on_bar(bar(T0 + 4 * H, 96.0), {**NOSIG, "enter": True, "stop": 90.0})
        self.assertEqual(dec["action"], "SKIP")                                   # no new entries today
        self.assertEqual(e.s["pending"], None)
        nxt = T0 + 30 * H                                                          # next calendar day
        _, dec = e.on_bar(bar(nxt, 96.0), {**NOSIG, "enter": True, "stop": 90.0})
        self.assertEqual(dec["action"], "BUY_NEXT_OPEN")

    def test_no_leverage_cash_never_negative(self):
        c = cfg(max_position_pct=100, risk_per_trade_pct=100)
        df = synthetic(1500, seed=11)
        for st in load_all():
            sig = st.signals(df)
            m, trades, equity, _ = run_range(st, sig, c, 250, len(df), "15m")
            for t in trades:
                if t["side"] == "BUY":
                    self.assertLessEqual(t["value"] + t["fee"], 10000 * 10)       # sanity
            self.assertTrue(all(x > 0 for x in equity))

    def test_buy_never_exceeds_cash(self):
        e = Engine(cfg(max_position_pct=100, risk_per_trade_pct=100))
        e.on_bar(bar(T0, 100.0), {**NOSIG, "enter": True, "stop": 99.0})
        e.on_bar(bar(T0 + H, 100.0), NOSIG)
        self.assertGreaterEqual(e.s["cash"], 0)

    def test_leverage_and_short_refused(self):
        import json
        from btcpaper import config as C
        with self.assertRaises(ValueError):
            Engine(cfg(leverage=3))
        with self.assertRaises(ValueError):
            Engine(cfg(allow_short=True))

    def test_restart_does_not_reprocess_candles(self):
        e = Engine(cfg())
        e.on_bar(bar(T0, 100.0), {**NOSIG, "enter": True, "stop": 95.0})
        ev, dec = e.on_bar(bar(T0, 100.0), {**NOSIG, "enter": True, "stop": 95.0})
        self.assertEqual((ev, dec), ([], None))


if __name__ == "__main__":
    unittest.main()
