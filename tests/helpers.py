import numpy as np
import pandas as pd

from btcpaper.config import DEFAULTS


def cfg(**kw):
    c = dict(DEFAULTS)
    c.update(kw)
    return c


def synthetic(n=1200, seed=3, step_ms=900_000):
    rng = np.random.default_rng(seed)
    close = 60000 * np.exp(np.cumsum(rng.normal(0, 0.004, n)))
    open_ = np.r_[close[0], close[:-1]]
    high = np.maximum(open_, close) * (1 + rng.uniform(0, 0.002, n))
    low = np.minimum(open_, close) * (1 - rng.uniform(0, 0.002, n))
    ts = 1_700_000_000_000 + np.arange(n) * step_ms
    df = pd.DataFrame({"ts": ts, "open": open_, "high": high, "low": low, "close": close, "volume": 1.0})
    df["time"] = pd.to_datetime(df["ts"], unit="ms", utc=True)
    return df


def bar(ts, o, h=None, l=None, c=None):
    c = o if c is None else c
    return {"ts": ts, "open": o, "high": h if h is not None else max(o, c), "low": l if l is not None else min(o, c), "close": c}


NOSIG = {"enter": False, "exit": False, "stop": float("nan"), "trail_stop": None, "note": ""}
