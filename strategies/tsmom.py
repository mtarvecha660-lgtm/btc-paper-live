"""Time-series momentum ("dual momentum" with cash as the alternative): hold BTC while its return over
the last N days (completed daily closes) is positive, else cash. Allocation strategy, crash stop always set."""
from btcpaper.indicators import daily_close_prev, daily_return_prev

NAME = "tsmom"
DESCRIPTION = "Hold BTC while its 3- or 6-month return is positive, else cash."
PARAMS = {"lookback_days": 180, "crash_stop_pct": 30}
GRID = {"lookback_days": [90, 180]}


def compute(df, p):
    out = df.copy()
    out["mom"] = daily_return_prev(out, p["lookback_days"]) * 100
    ready = out["mom"].notna()
    up = ready & (out["mom"] > 0)
    out["enter"] = up
    out["exit"] = ready & ~up
    out["stop"] = out["close"] * (1 - p["crash_stop_pct"] / 100)
    out["note"] = str(p["lookback_days"]) + "d return " + out["mom"].round(1).astype(str) + "%"
    return out
