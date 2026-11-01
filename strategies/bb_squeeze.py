"""Bollinger squeeze breakout: when the bands get unusually narrow (a quiet market), wait for a close
above the upper band and buy the breakout. Sell on a close back below the middle band. ATR stop that
trails up. Meant for 4h candles."""
from btcpaper.indicators import atr

NAME = "bb_squeeze"
DESCRIPTION = "Bands squeeze (quiet market), then a close above the upper band -> buy. Exit below the middle band. ATR stop."
PARAMS = {"n": 20, "k": 2.0, "squeeze_lookback": 120, "squeeze_q": 0.2, "recent": 6, "atr_period": 14, "atr_mult": 2.5}
GRID = {"n": [20, 30], "squeeze_q": [0.1, 0.25], "atr_mult": [2.0, 3.0]}


def compute(df, p):
    out = df.copy()
    mid = out["close"].rolling(p["n"]).mean()
    sd = out["close"].rolling(p["n"]).std()
    upper, lower = mid + p["k"] * sd, mid - p["k"] * sd
    width = (upper - lower) / mid
    thresh = width.rolling(p["squeeze_lookback"]).quantile(p["squeeze_q"])
    squeezed = (width <= thresh).astype(float).rolling(p["recent"]).max() > 0
    out["atr"] = atr(out, p["atr_period"])
    out["enter"] = squeezed & (out["close"] > upper)
    out["exit"] = out["close"] < mid
    out["stop"] = out["close"] - p["atr_mult"] * out["atr"]
    out["trail_stop"] = out["close"] - p["atr_mult"] * out["atr"]
    out["note"] = ("width " + (width * 100).round(2).astype(str) + "% (squeeze <= " + (thresh * 100).round(2).astype(str)
                   + "%) upper " + upper.round(0).astype(str) + " mid " + mid.round(0).astype(str))
    return out
