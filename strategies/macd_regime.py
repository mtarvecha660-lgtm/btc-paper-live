"""MACD crossover, but only when BTC is in an uptrend (last daily close above its 200-day SMA).
Buy when the MACD line crosses above its signal line; sell when it crosses back below or the trend
filter turns off. ATR stop. Meant for 4h candles."""
from btcpaper.indicators import ema, atr, crossed_above, crossed_below, daily_close_prev

NAME = "macd_regime"
DESCRIPTION = "MACD cross up while above the 200-day SMA -> buy; cross down or trend off -> sell. ATR stop."
PARAMS = {"fast": 12, "slow": 26, "signal": 9, "sma_days": 200, "atr_period": 14, "atr_mult": 3.0}
GRID = {"fast": [8, 12], "slow": [21, 26], "atr_mult": [2.0, 3.0]}


def compute(df, p):
    out = df.copy()
    macd = ema(out["close"], p["fast"]) - ema(out["close"], p["slow"])
    sig = ema(macd, p["signal"])
    out["macd"], out["macd_sig"] = macd, sig
    dclose, dsma = daily_close_prev(out, p["sma_days"])
    regime = dsma.notna() & (dclose > dsma)
    out["atr"] = atr(out, p["atr_period"])
    out["enter"] = crossed_above(macd, sig) & regime
    out["exit"] = crossed_below(macd, sig) | (dsma.notna() & ~regime)
    out["stop"] = out["close"] - p["atr_mult"] * out["atr"]
    out["note"] = ("macd " + macd.round(0).astype(str) + " sig " + sig.round(0).astype(str)
                   + " | trend " + regime.map({True: "up", False: "off"}))
    return out
