"""Public market data only. No API keys, no account access, no order endpoints.

Candles come from the first source in config["sources"] that answers.
Binance's main API answers HTTP 451 from some countries; binance_vision is
Binance's public data mirror and usually works where the main API is blocked.
"""
import time
from datetime import datetime, timezone

import pandas as pd
import requests

from .config import DATA_DIR, tf_minutes

COLS = ["ts", "open", "high", "low", "close", "volume"]
UA = {"User-Agent": "btcpaper/1.0 (paper trading kit)"}


class DataError(Exception):
    pass


def _now_ms():
    return int(time.time() * 1000)


# ---------- Binance (direct public REST: no keys, no exchangeInfo call) ----------
def _binance_like(base, symbol, tf, since_ms, until_ms):
    sym = symbol.replace("/", "")
    out, cur = [], since_ms
    step = tf_minutes(tf) * 60_000
    while cur < until_ms:
        r = requests.get(f"{base}/api/v3/klines", params={"symbol": sym, "interval": tf, "startTime": cur,
                                                           "endTime": until_ms, "limit": 1000},
                         headers=UA, timeout=20)
        if r.status_code != 200:
            raise DataError(f"HTTP {r.status_code}: {r.text[:120]}")
        rows = r.json()
        if not rows:
            break
        out += [[int(k[0]), float(k[1]), float(k[2]), float(k[3]), float(k[4]), float(k[5])] for k in rows]
        nxt = int(rows[-1][0]) + step
        if nxt <= cur:
            break
        cur = nxt
        if len(rows) < 1000:
            break
    return out


def _fetch_binance(symbol, tf, since_ms, until_ms):
    return _binance_like("https://api.binance.com", symbol, tf, since_ms, until_ms)


def _fetch_binance_vision(symbol, tf, since_ms, until_ms):
    return _binance_like("https://data-api.binance.vision", symbol, tf, since_ms, until_ms)


# ---------- other exchanges through ccxt (public endpoints only) ----------
_CCXT_LIMIT = {"okx": 100, "bitstamp": 1000, "coinbase": 300, "kraken": 720}


def _fetch_ccxt(name, symbol, tf, since_ms, until_ms):
    import ccxt  # imported lazily: only needed for fallbacks
    ex = getattr(ccxt, name)({"enableRateLimit": True, "timeout": 20000})  # no apiKey, ever
    sym = symbol
    if name in ("coinbase", "kraken"):
        # USDT pairs are thin or missing there; BTC/USD tracks BTC/USDT within a few tenths of a %.
        sym = symbol.replace("/USDT", "/USD")
    lim = _CCXT_LIMIT.get(name, 500)
    step = tf_minutes(tf) * 60_000
    out, cur = [], since_ms
    for _ in range(5000):
        if cur >= until_ms:
            break
        rows = ex.fetch_ohlcv(sym, tf, since=cur, limit=lim)
        rows = [r for r in rows if r[0] >= cur]
        if not rows:
            break
        out += [[int(r[0])] + [float(x) for x in r[1:6]] for r in rows]
        nxt = int(rows[-1][0]) + step
        if nxt <= cur:
            break
        cur = nxt
        if name == "kraken":   # kraken only serves the latest 720 candles
            break
    return out


FETCHERS = {
    "binance": _fetch_binance,
    "binance_vision": _fetch_binance_vision,
    "okx": lambda s, t, a, b: _fetch_ccxt("okx", s, t, a, b),
    "bitstamp": lambda s, t, a, b: _fetch_ccxt("bitstamp", s, t, a, b),
    "coinbase": lambda s, t, a, b: _fetch_ccxt("coinbase", s, t, a, b),
    "kraken": lambda s, t, a, b: _fetch_ccxt("kraken", s, t, a, b),
}


def _to_df(rows):
    df = pd.DataFrame(rows, columns=COLS)
    df = df.drop_duplicates("ts").sort_values("ts").reset_index(drop=True)
    df["time"] = pd.to_datetime(df["ts"], unit="ms", utc=True)
    return df


def drop_unclosed(df, tf, now_ms=None):
    """Remove the candle that is still forming. Strategies only ever see closed candles."""
    now_ms = now_ms or _now_ms()
    step = tf_minutes(tf) * 60_000
    return df[df["ts"] + step <= now_ms].reset_index(drop=True)


def _cache_path(source, symbol, tf):
    return DATA_DIR / f"{source}_{symbol.replace('/', '')}_{tf}.csv"


def fetch(symbol, tf, since_ms, until_ms=None, sources=None, verbose=True, use_cache=True, keep_forming=False):
    """Closed candles in [since_ms, until_ms). Returns (df, source_name).

    Tries each source in order; a cached CSV per source is topped up instead of re-downloaded.
    keep_forming=True also returns the candle that is still forming (live loop only; never cached,
    never shown to a strategy).
    """
    until_ms = until_ms or _now_ms()
    sources = sources or ["binance", "binance_vision", "okx", "bitstamp", "coinbase", "kraken"]
    step = tf_minutes(tf) * 60_000
    errors = []
    for src in sources:
        if src not in FETCHERS:
            errors.append(f"{src}: unknown source")
            continue
        try:
            cached = pd.DataFrame(columns=COLS)
            cp = _cache_path(src, symbol, tf)
            if use_cache and cp.exists():
                cached = pd.read_csv(cp)[COLS]
                cached = cached[(cached["ts"] >= since_ms)]
            rows = []
            if len(cached) and cached["ts"].min() <= since_ms + step:
                start = int(cached["ts"].max()) + step     # only top up the tail
            else:
                cached = pd.DataFrame(columns=COLS)
                start = since_ms
            if start < until_ms:
                rows = FETCHERS[src](symbol, tf, start, until_ms)
            df = _to_df(cached.values.tolist() + rows)
            df = df[(df["ts"] >= since_ms) & (df["ts"] < until_ms)]
            forming = df[df["ts"] + step > _now_ms()]
            df = drop_unclosed(df, tf)
            if len(df) == 0:
                raise DataError("no candles returned")
            expected = (min(until_ms, _now_ms()) - since_ms) // step
            if expected > 50 and len(df) < 0.9 * expected:
                raise DataError(f"only {len(df)} of ~{expected} candles (source has short history)")
            if use_cache:
                DATA_DIR.mkdir(exist_ok=True)
                old = pd.read_csv(cp)[COLS] if cp.exists() else pd.DataFrame(columns=COLS)
                allc = _to_df(old.values.tolist() + df[COLS].values.tolist())
                allc[COLS].to_csv(cp, index=False)
            if verbose:
                print(f"[data] {len(df)} {tf} candles from {src} "
                      f"({df['time'].iloc[0]:%Y-%m-%d %H:%M} -> {df['time'].iloc[-1]:%Y-%m-%d %H:%M} UTC)")
            if keep_forming and len(forming):
                df = pd.concat([df, forming.tail(1)])
            return df.reset_index(drop=True), src
        except Exception as e:  # blocked, geo-restricted, rate-limited, offline...
            msg = f"{src}: {type(e).__name__}: {str(e)[:140]}"
            errors.append(msg)
            if verbose:
                print(f"[data] {msg} -> trying next source")
    # No network (e.g. an AI agent's sandbox) -> fall back to candles cached by an earlier run.
    if use_cache:
        for src in sources:
            cp = _cache_path(src, symbol, tf)
            if not cp.exists():
                continue
            df = _to_df(pd.read_csv(cp)[COLS].values.tolist())
            df = df[(df["ts"] >= since_ms) & (df["ts"] < until_ms)].reset_index(drop=True)
            if len(df) and df["ts"].iloc[0] <= since_ms + 2 * step:
                if verbose:
                    print(f"[data] WARNING: no live source answered; using {len(df)} cached {tf} candles from {src}, "
                          f"newest {df['time'].iloc[-1]:%Y-%m-%d %H:%M} UTC (may be stale)")
                return df, f"{src} (cached, offline)"
    raise DataError("every data source failed:\n  " + "\n  ".join(errors))


def fetch_days(symbol, tf, days, warmup_bars=0, sources=None, verbose=True):
    step = tf_minutes(tf) * 60_000
    until = (_now_ms() // step) * step
    since = until - int(days * 86_400_000) - warmup_bars * step
    return fetch(symbol, tf, since, until, sources, verbose)


def last_price(symbol, sources=None):
    """Latest traded price (from the newest 1m candle, closed or not)."""
    for src in (sources or ["binance", "binance_vision", "okx", "bitstamp", "coinbase", "kraken"]):
        try:
            rows = FETCHERS[src](symbol, "1m", _now_ms() - 5 * 60_000, _now_ms() + 60_000)
            if rows:
                return rows[-1][4], src
        except Exception:
            continue
    return None, None


_INR_CACHE = {"t": 0, "rate": None, "src": None}


def usdt_inr(fallback=88.0):
    """USDT->INR rate. CoinGecko (tether in INR), then a USD->INR FX API, then the config fallback."""
    if _INR_CACHE["rate"] and time.time() - _INR_CACHE["t"] < 3600:
        return _INR_CACHE["rate"], _INR_CACHE["src"]
    tries = [
        ("coingecko", "https://api.coingecko.com/api/v3/simple/price?ids=tether&vs_currencies=inr",
         lambda j: j["tether"]["inr"]),
        ("open.er-api", "https://open.er-api.com/v6/latest/USD", lambda j: j["rates"]["INR"]),
    ]
    for name, url, pick in tries:
        try:
            r = requests.get(url, headers=UA, timeout=10)
            rate = float(pick(r.json()))
            if 30 < rate < 300:
                _INR_CACHE.update(t=time.time(), rate=rate, src=name)
                return rate, name
        except Exception:
            continue
    return float(fallback), "fallback (config usd_inr_fallback, may be stale)"


def fmt_ts(ms):
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
