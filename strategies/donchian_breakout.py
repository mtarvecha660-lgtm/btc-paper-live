"""Donchian breakout (turtle-style): buy when the close breaks above the highest high of the
previous N candles; sell when it breaks below the lowest low of the previous M candles.
ATR stop that trails up (never down)."""
from btcpaper.indicators import donchian, atr

NAME = "donchian_breakout"
DESCRIPTION = "Close breaks the previous 55-candle high -> buy; breaks the previous 20-candle low -> sell. Trailing ATR stop."
PARAMS = {"entry_n": 55, "exit_n": 20, "atr_period": 20, "atr_mult": 3.0}
GRID = {"entry_n": [20, 55, 100], "exit_n": [10, 20], "atr_mult": [2.0, 3.0]}


def compute(df, p):
    out = df.copy()
    out["dc_high"], _ = donchian(out, p["entry_n"])
    _, out["dc_low"] = donchian(out, p["exit_n"])
    out["atr"] = atr(out, p["atr_period"])
    out["enter"] = out["close"] > out["dc_high"]
    out["exit"] = out["close"] < out["dc_low"]
    out["stop"] = out["close"] - p["atr_mult"] * out["atr"]
    out["trail_stop"] = out["stop"]            # engine raises the stop to this each candle, never lowers it
    out["note"] = "hi" + str(p["entry_n"]) + "=" + out["dc_high"].round(0).astype(str) + " lo" + str(p["exit_n"]) + "=" + out["dc_low"].round(0).astype(str)
    out.loc[out["enter"], "note"] = "close broke the " + str(p["entry_n"]) + "-candle high | " + out["note"]
    out.loc[out["exit"], "note"] = "close broke the " + str(p["exit_n"]) + "-candle low | " + out["note"]
    return out
