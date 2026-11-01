"""RSI mean-reversion: buy a short-term oversold dip (RSI below 'low') while the longer trend is up;
sell when RSI recovers above 'exit_rsi'. ATR stop below the dip."""
from btcpaper.indicators import rsi, atr, ema, crossed_above

NAME = "rsi_meanrev"
DESCRIPTION = "RSI drops below 30 while price is above the 200 EMA -> buy the dip; RSI back above 55 -> sell. ATR stop."
PARAMS = {"rsi_period": 14, "low": 30, "exit_rsi": 55, "trend": 200, "atr_period": 14, "atr_mult": 2.0}
GRID = {"low": [25, 30, 35], "exit_rsi": [50, 60], "atr_mult": [1.5, 2.5]}


def compute(df, p):
    out = df.copy()
    out["rsi"] = rsi(out["close"], p["rsi_period"])
    out["ema_trend"] = ema(out["close"], p["trend"])
    out["atr"] = atr(out, p["atr_period"])
    # enter on the candle where RSI turns back up from oversold (less 'falling knife' than buying the first touch)
    out["enter"] = crossed_above(out["rsi"], p["low"]) & (out["close"] > out["ema_trend"])
    out["exit"] = out["rsi"] > p["exit_rsi"]
    out["stop"] = out["close"] - p["atr_mult"] * out["atr"]
    out["note"] = "rsi=" + out["rsi"].round(1).astype(str) + " trend=" + out["ema_trend"].round(0).astype(str)
    out.loc[out["enter"], "note"] = "RSI turned up through " + str(p["low"]) + " in an uptrend | " + out["note"]
    out.loc[out["exit"], "note"] = "RSI above " + str(p["exit_rsi"]) + " (bounce done) | " + out["note"]
    return out
