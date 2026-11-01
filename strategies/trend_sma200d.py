"""Trend filter: hold BTC only while the last DAILY close is above its N-day simple moving average
(the classic 200-day rule); otherwise sit in cash. Runs on any intraday timeframe, but the signal only
changes once a day (at 00:00 UTC, using the day that just closed). Allocation strategy: when in, it
holds a full position (the live account sets risk/max-position to 100%); a wide crash stop is always set."""
from btcpaper.indicators import daily_close_prev

NAME = "trend_sma200d"
DESCRIPTION = "Hold BTC while the last daily close is above its 200-day SMA, else cash."
PARAMS = {"sma_days": 200, "crash_stop_pct": 30}
GRID = {"sma_days": [100, 150, 200]}


def compute(df, p):
    out = df.copy()
    dclose, dsma = daily_close_prev(out, p["sma_days"])
    out["d_close"], out["d_sma"] = dclose, dsma
    ready = out["d_sma"].notna()
    above = ready & (out["d_close"] > out["d_sma"])
    out["enter"] = above
    out["exit"] = ready & ~above
    out["stop"] = out["close"] * (1 - p["crash_stop_pct"] / 100)
    out["note"] = ("daily close " + out["d_close"].round(0).astype(str) + " vs " + str(p["sma_days"])
                   + "d SMA " + out["d_sma"].round(0).astype(str))
    return out
