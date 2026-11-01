"""`python -m btcpaper check`: rejects strategies that peek at the future.

Two tests:
 1. static scan of the source for the usual look-ahead mistakes;
 2. the real test: signals computed on the full history must equal signals computed when the
    data is cut off at that candle. If row i changes when later candles are added, the strategy
    used the future. This catches tricks the static scan can't see.
"""
import re

import numpy as np
import pandas as pd

from . import data as D
from .config import DATA_DIR
from .strategies import load, strategy_files

BANNED = [
    (r"\.shift\(\s*(periods\s*=\s*)?-\s*\d", "shift(-n) reads FUTURE candles"),
    (r"center\s*=\s*True", "centered rolling window uses future candles"),
    (r"\.bfill\(|backfill|method\s*=\s*[\'\"]bfill", "back-fill copies future values backwards"),
    (r"iloc\[[^\]]*\+\s*\d+\s*\]", "iloc[i+1] reads the next candle"),
    (r"\.iloc\[\s*-\s*1\s*\]|\.tail\(", "the last row of the WHOLE dataset is the future for earlier rows"),
    (r"\[\s*[\'\"](close|open|high|low)[\'\"]\s*\]\s*\.(max|min|mean|std|median|quantile)\(\s*\)",
     "a whole-column statistic (e.g. close.max()) includes future prices; use .rolling(n) or .expanding()"),
]


def static_scan(path):
    src = path.read_text(encoding="utf-8")
    problems = []
    for ln, line in enumerate(src.splitlines(), 1):
        code = line.split("#", 1)[0]
        for pat, why in BANNED:
            if re.search(pat, code):
                problems.append(f"line {ln}: {why}: {line.strip()}")
    return problems


def sample_data(n=1500):
    """Real cached candles if we have them, else fetch, else a synthetic random walk (offline)."""
    for f in sorted(DATA_DIR.glob("*_BTCUSDT_*.csv")):
        df = pd.read_csv(f)
        if len(df) >= 600:
            df = df.tail(n).reset_index(drop=True)
            df["time"] = pd.to_datetime(df["ts"], unit="ms", utc=True)
            return df, f.name
    try:
        df, src = D.fetch_days("BTC/USDT", "1h", 60, verbose=False)
        return df, f"{src} 1h"
    except Exception:
        pass
    rng = np.random.default_rng(7)
    close = 60000 * np.exp(np.cumsum(rng.normal(0, 0.004, n)))
    open_ = np.r_[close[0], close[:-1]]
    high = np.maximum(open_, close) * (1 + rng.uniform(0, 0.003, n))
    low = np.minimum(open_, close) * (1 - rng.uniform(0, 0.003, n))
    ts = 1_700_000_000_000 + np.arange(n) * 3_600_000
    df = pd.DataFrame({"ts": ts, "open": open_, "high": high, "low": low, "close": close,
                       "volume": rng.uniform(1, 100, n)})
    df["time"] = pd.to_datetime(df["ts"], unit="ms", utc=True)
    return df, "synthetic random walk (offline)"


def _same(a, b):
    if a.dtype == bool or b.dtype == bool:
        return np.array_equal(a.astype(bool), b.astype(bool))
    a, b = a.astype(float), b.astype(float)
    return bool(np.all((np.isnan(a) & np.isnan(b)) | np.isclose(a, b, rtol=1e-9, atol=1e-9)))


def dynamic_check(strategy, df, cuts=40):
    full = strategy.signals(df)
    cols = [c for c in ("enter", "exit", "stop", "trail_stop") if c in full]
    n = len(df)
    points = sorted(set(np.linspace(max(50, n // 5), n - 2, cuts).astype(int)))
    bad = []
    for k in points:
        part = strategy.signals(df.iloc[: k + 1].reset_index(drop=True))
        for c in cols:
            if not _same(full[c].iloc[: k + 1].values, part[c].values):
                diff = np.where(~((full[c].iloc[: k + 1].values == part[c].values) |
                                  (pd.isna(full[c].iloc[: k + 1].values) & pd.isna(part[c].values))))[0]
                first = int(diff[0]) if len(diff) else k
                bad.append(f"column '{c}' at candle {first} changes when candles after {k} are added")
                break
        if len(bad) >= 3:
            break
    stats = {"entries": int(full["enter"].sum()), "exits": int(full["exit"].sum()),
             "bad_stops": int(((full["enter"]) & ~(full["stop"] < full["close"])).sum())}
    return bad, stats


def check(names=None, verbose=True):
    files = strategy_files()
    targets = names or [f.stem for f in files]
    df, src = sample_data()
    if verbose:
        print(f"[check] test data: {len(df)} candles ({src})")
    all_ok = True
    report = {}
    for name in targets:
        st = load(name)
        problems = static_scan(st.path)
        try:
            bad, stats = dynamic_check(st, df)
        except Exception as e:
            bad, stats = [f"compute() crashed: {type(e).__name__}: {e}"], {}
        warn = []
        if stats.get("bad_stops"):
            bad.append(f"{stats['bad_stops']} entry signals have no stop below the close")
        if stats and stats.get("entries", 0) == 0:
            warn.append("no entry signals on the test data (strategy never trades?)")
        ok = not problems and not bad
        all_ok &= ok
        report[st.name] = {"ok": ok, "static": problems, "dynamic": bad, "warnings": warn, **stats}
        if verbose:
            print(f"  {'PASS' if ok else 'FAIL'}  {st.name}  ({stats.get('entries', '?')} entries on test data)")
            for p in problems:
                print(f"        static: {p}")
            for p in bad:
                print(f"        look-ahead: {p}")
            for w in warn:
                print(f"        warning: {w}")
    return all_ok, report
