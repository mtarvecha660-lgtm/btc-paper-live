"""Causal indicators: every value at row i uses rows <= i only (no centered windows, no negative shifts)."""
import numpy as np
import pandas as pd


def ema(s, n):
    return s.ewm(span=n, adjust=False, min_periods=n).mean()


def sma(s, n):
    return s.rolling(n, min_periods=n).mean()


def rsi(close, n=14):
    d = close.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    rs = up / dn.replace(0, np.nan)
    out = 100 - 100 / (1 + rs)
    return out.where(dn != 0, 100.0)


def atr(df, n=14):
    pc = df["close"].shift(1)
    tr = pd.concat([df["high"] - df["low"], (df["high"] - pc).abs(), (df["low"] - pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()


def donchian(df, n):
    """Highest high / lowest low of the PREVIOUS n candles (excludes the current candle),
    so 'close > upper' means a real breakout of the prior range."""
    return df["high"].rolling(n, min_periods=n).max().shift(1), df["low"].rolling(n, min_periods=n).min().shift(1)


def _prev(x):
    return x.shift(1) if isinstance(x, pd.Series) else x       # a number (e.g. 30) has no "previous"


def crossed_above(a, b):
    """True on the candle where a goes from <= b to > b. b can be a Series or a number."""
    return (a > b) & (_prev(a) <= _prev(b))


def crossed_below(a, b):
    return (a < b) & (_prev(a) >= _prev(b))
