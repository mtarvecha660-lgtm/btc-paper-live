"""TEMPLATE: copy this file to strategies/my_idea.py, rename NAME, write compute().
Files starting with "_" are ignored by the loader. Read STRATEGY_GUIDE.md first.

Rules (python -m btcpaper check enforces them):
  * compute(df, p) gets CLOSED candles only: columns ts, time, open, high, low, close, volume.
  * Row i may use rows <= i only. No .shift(-1), no center=True, no bfill, no df.iloc[i+1].
  * Return a copy of df with:
      enter (bool)  buy at the NEXT candle's open
      exit  (bool)  sell at the NEXT candle's open
      stop  (float) absolute stop-loss price for an entry on this row (must be below close)
    optional: trail_stop (float, stop ratchets up to it), note (str, shown in the decision log)
"""
from btcpaper.indicators import ema, atr

NAME = "my_idea"
DESCRIPTION = "One line saying what it does."
PARAMS = {"n": 50, "atr_period": 14, "atr_mult": 2.0}
GRID = {"n": [20, 50, 100]}


def compute(df, p):
    out = df.copy()
    out["ma"] = ema(out["close"], p["n"])
    out["atr"] = atr(out, p["atr_period"])
    out["enter"] = (out["close"] > out["ma"]) & (out["close"].shift(1) <= out["ma"].shift(1))
    out["exit"] = out["close"] < out["ma"]
    out["stop"] = out["close"] - p["atr_mult"] * out["atr"]
    out["note"] = "ma=" + out["ma"].round(0).astype(str)
    return out
