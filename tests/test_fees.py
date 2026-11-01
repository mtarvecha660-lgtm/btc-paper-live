import unittest

from btcpaper.engine import Engine
from tests.helpers import cfg, bar, NOSIG

H = 3_600_000
T0 = 1_700_000_000_000


class FeeMath(unittest.TestCase):
    def test_buy_fill_fee_and_slippage(self):
        e = Engine(cfg(fee_pct=0.1, slippage_pct=0.05, max_position_pct=50, risk_per_trade_pct=100))
        e.on_bar(bar(T0, 100.0), {**NOSIG, "enter": True, "stop": 90.0})        # signal on close of candle 0
        ev, _ = e.on_bar(bar(T0 + H, 200.0), NOSIG)                              # fills at candle 1 OPEN
        buy = ev[0]
        self.assertAlmostEqual(buy["price"], 200.0 * 1.0005)                     # slippage against us
        self.assertAlmostEqual(buy["value"], 5000.0)                             # 50% of 10,000
        self.assertAlmostEqual(buy["fee"], 5.0)                                  # 0.1% of 5,000
        self.assertAlmostEqual(e.s["cash"], 10000 - 5000 - 5)
        self.assertAlmostEqual(buy["qty"], 5000 / (200 * 1.0005))

    def test_round_trip_flat_price_loses_fees_and_slippage(self):
        e = Engine(cfg(fee_pct=0.1, slippage_pct=0.05, max_position_pct=50, risk_per_trade_pct=100))
        e.on_bar(bar(T0, 100.0), {**NOSIG, "enter": True, "stop": 90.0})
        e.on_bar(bar(T0 + H, 100.0), {**NOSIG, "exit": True})
        ev, _ = e.on_bar(bar(T0 + 2 * H, 100.0), NOSIG)
        sell = ev[0]
        qty = 5000 / 100.05
        proceeds = qty * 100 * (1 - 0.0005)
        expected_pnl = proceeds * (1 - 0.001) - 5000 - 5
        self.assertAlmostEqual(sell["pnl"], expected_pnl, places=6)
        self.assertAlmostEqual(e.s["cash"], 10000 + expected_pnl, places=6)
        self.assertLess(sell["pnl"], 0)                                          # flat price = guaranteed loss
        self.assertAlmostEqual(e.s["fees_paid"], 5 + proceeds * 0.001, places=6)

    def test_signal_fills_next_open_not_same_close(self):
        e = Engine(cfg())
        ev, dec = e.on_bar(bar(T0, 100.0, c=150.0), {**NOSIG, "enter": True, "stop": 140.0})
        self.assertEqual(ev, [])                                                 # nothing filled on the signal candle
        self.assertEqual(dec["action"], "BUY_NEXT_OPEN")
        ev, _ = e.on_bar(bar(T0 + H, 151.0, h=152, l=150.5, c=151.5), NOSIG)
        self.assertAlmostEqual(ev[0]["price"], 151.0 * (1 + cfg()["slippage_pct"] / 100))

    def test_hold_benchmark_pays_fees(self):
        from btcpaper.metrics import summarize
        m = summarize([10000, 10000], [], "1h", 10000, [100.0, 100.0], 0.1, 0.05)
        self.assertLess(m["hold_return_pct"], 0)                                 # buying and selling costs something


if __name__ == "__main__":
    unittest.main()
