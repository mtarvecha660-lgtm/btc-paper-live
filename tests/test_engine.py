import json
import unittest

from btcpaper.backtest import run_range
from btcpaper.engine import Engine, new_state
from btcpaper.strategies import load
from tests.helpers import cfg, synthetic


class LiveMatchesBacktest(unittest.TestCase):
    def test_live_style_fills_match_backtest(self):
        """The live loop fills at the open as soon as a candle opens (on_open), and the state is saved to
        JSON and reloaded between candles (restart). Results must equal a straight backtest."""
        c = cfg()
        df = synthetic(1500, seed=5)
        st = load("donchian_breakout").with_params({"entry_n": 20, "exit_n": 10})
        sig = st.signals(df)
        m, trades_bt, eq_bt, _ = run_range(st, sig, c, 200, len(df), "15m")
        self.assertGreater(m["trades"], 5)

        state = new_state(c["starting_balance_usdt"])
        trades_live, eq_live = [], []
        for i in range(200, len(df)):
            eng = Engine(c, json.loads(json.dumps(state)))                # restart every candle
            r = df.iloc[i]
            evs, _ = eng.on_open(int(r["ts"]), float(r["open"]))          # candle opens -> pending fills now
            trades_live += evs
            s = sig.iloc[i]
            ev2, dec = eng.on_bar(r, {"enter": bool(s["enter"]), "exit": bool(s["exit"]), "stop": float(s["stop"]),
                                      "trail_stop": float(s["trail_stop"]), "note": ""})
            trades_live += ev2
            eq_live.append(dec["equity"])
            state = eng.s
        self.assertEqual(len(trades_live), len(trades_bt))
        for a, b in zip(trades_live, trades_bt):
            self.assertEqual(a["side"], b["side"])
            self.assertAlmostEqual(a["price"], b["price"])
        self.assertAlmostEqual(eq_live[-1], eq_bt[-1], places=6)


if __name__ == "__main__":
    unittest.main()
