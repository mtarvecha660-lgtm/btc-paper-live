import tempfile
import textwrap
import unittest
from pathlib import Path

from btcpaper.check import dynamic_check, static_scan
from btcpaper.strategies import load, load_all
from tests.helpers import synthetic


def _strategy_from_source(src):
    d = Path(tempfile.mkdtemp())
    f = d / "cheat.py"
    f.write_text(textwrap.dedent(src), encoding="utf-8")
    return load(str(f)), f


CHEAT_SHIFT = """
from btcpaper.indicators import atr
NAME = "cheat_shift"
PARAMS = {}
def compute(df, p):
    out = df.copy()
    out["enter"] = out["close"].shift(-1) > out["close"]      # peeks at the next candle
    out["exit"] = out["close"].shift(-1) < out["close"]
    out["stop"] = out["close"] * 0.98
    return out
"""

CHEAT_HIDDEN = """
NAME = "cheat_hidden"
PARAMS = {}
def compute(df, p):
    out = df.copy()
    top = out["close"].rolling(len(out)).max().iloc[len(out) - 1]   # whole-history max, hidden from the regexes
    out["enter"] = out["close"] < top * 0.9
    out["exit"] = out["close"] > top * 0.99
    out["stop"] = out["close"] * 0.98
    return out
"""


class LookAhead(unittest.TestCase):
    df = synthetic(900)

    def test_builtin_strategies_pass(self):
        for st in load_all():
            bad, stats = dynamic_check(st, self.df, cuts=15)
            self.assertEqual(bad, [], f"{st.name}: {bad}")
            self.assertEqual(static_scan(st.path), [], st.name)
            self.assertEqual(stats["bad_stops"], 0, st.name)

    def test_shift_minus_one_is_rejected(self):
        st, f = _strategy_from_source(CHEAT_SHIFT)
        self.assertTrue(static_scan(f))
        bad, _ = dynamic_check(st, self.df, cuts=10)
        self.assertTrue(bad)

    def test_hidden_future_peek_is_caught_dynamically(self):
        st, f = _strategy_from_source(CHEAT_HIDDEN)
        bad, _ = dynamic_check(st, self.df, cuts=10)
        self.assertTrue(bad, "dynamic check should catch whole-history statistics")


if __name__ == "__main__":
    unittest.main()
