"""EMA crossover: buy when the fast EMA crosses above the slow EMA (trend turning up),
only if price is above the long trend EMA. Sell when it crosses back below. ATR stop."""
from btcpaper.indicators import ema, atr, crossed_above, crossed_below

NAME = "ema_cross"
DESCRIPTION = "Fast EMA crosses above slow EMA (with trend filter) -> buy; crosses below -> sell. ATR stop."
PARAMS = {"fast": 20, "slow": 50, "trend": 200, "atr_period": 14, "atr_mult": 2.5}
GRID = {"fast": [10, 20, 30], "slow": [50, 100], "atr_mult": [2.0, 3.0]}   # used by --optimize


def compute(df, p):
    out = df.copy()
    out["ema_fast"] = ema(out["close"], p["fast"])
    out["ema_slow"] = ema(out["close"], p["slow"])
    out["ema_trend"] = ema(out["close"], p["trend"])
    out["atr"] = atr(out, p["atr_period"])
    up = crossed_above(out["ema_fast"], out["ema_slow"])
    out["enter"] = up & (out["close"] > out["ema_trend"])
    out["exit"] = crossed_below(out["ema_fast"], out["ema_slow"])
    out["stop"] = out["close"] - p["atr_mult"] * out["atr"]
    out["note"] = ("ema" + str(p["fast"]) + "=" + out["ema_fast"].round(0).astype(str)
                   + " ema" + str(p["slow"]) + "=" + out["ema_slow"].round(0).astype(str)
                   + " trend=" + out["ema_trend"].round(0).astype(str))
    out.loc[out["enter"], "note"] = "fast EMA crossed above slow EMA, price above trend EMA | " + out["note"]
    out.loc[out["exit"], "note"] = "fast EMA crossed below slow EMA | " + out["note"]
    return out
