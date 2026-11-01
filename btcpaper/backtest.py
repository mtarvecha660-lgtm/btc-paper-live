"""Backtests with fees, slippage, next-open fills, stops, risk limits and a train/test split."""
import itertools
import json
import os
from datetime import datetime, timezone

import pandas as pd

from . import data as D
from .config import RESULTS_DIR, tf_minutes
from .engine import Engine, new_state
from .metrics import summarize


def run_range(strategy, sig, cfg, start_i, end_i, tf, collect=False):
    """Simulate candles [start_i, end_i) of a precomputed signal frame with a fresh balance."""
    eng = Engine(cfg, new_state(cfg["starting_balance_usdt"]))
    trades, equity, decisions, in_mkt = [], [], [], 0
    cols = sig.columns
    has_trail = "trail_stop" in cols
    E, X, S = sig["enter"].values, sig["exit"].values, sig["stop"].values
    T = sig["trail_stop"].values if has_trail else None
    N = sig["note"].values
    TS, O, H, L, C = (sig[k].values for k in ("ts", "open", "high", "low", "close"))
    for i in range(start_i, end_i):
        bar = {"ts": TS[i], "open": O[i], "high": H[i], "low": L[i], "close": C[i]}
        s = {"enter": bool(E[i]), "exit": bool(X[i]), "stop": float(S[i]),
             "trail_stop": float(T[i]) if has_trail else None, "note": N[i] if collect else ""}
        ev, dec = eng.on_bar(bar, s)
        trades += ev
        equity.append(dec["equity"])
        in_mkt += eng.in_position()
        if collect and dec["action"] != "WAIT":
            decisions.append(dec)
    m = summarize(equity, trades, tf, cfg["starting_balance_usdt"], list(C[start_i:end_i]),
                  cfg["fee_pct"], cfg["slippage_pct"], in_mkt)
    m["open_position"] = eng.in_position()
    return m, trades, equity, decisions


def _split_index(n_total, warm, train_pct):
    return warm + int((n_total - warm) * train_pct / 100)


def optimize(strategy, df, cfg, start_i, end_i, tf, min_trades=5):
    """Grid-search the strategy's GRID on candles [start_i, end_i) only. Ranked by Sharpe."""
    if not strategy.grid:
        return strategy.params, []
    keys = list(strategy.grid)
    rows = []
    for combo in itertools.product(*[strategy.grid[k] for k in keys]):
        st = strategy.with_params(dict(zip(keys, combo)))
        sig = st.signals(df)
        m, *_ = run_range(st, sig, cfg, start_i, end_i, tf)
        rows.append((dict(zip(keys, combo)), m))
    ok = [r for r in rows if r[1]["trades"] >= min_trades] or rows
    best = max(ok, key=lambda r: r[1]["sharpe"])
    return {**strategy.params, **best[0]}, rows


def backtest(strategy, cfg, tf, days, do_optimize=False, walk_forward=0, df=None, source=None, save=True, quiet=False):
    warm = cfg["warmup_bars"]
    if df is None:
        df, source = D.fetch_days(cfg["symbol"], tf, days, warm, cfg["sources"], verbose=not quiet)
    n = len(df)
    warm = min(warm, n // 5)
    split = _split_index(n, warm, cfg["train_pct"])
    result = {"strategy": strategy.name, "tf": tf, "days": days, "source": source, "symbol": cfg["symbol"],
              "from": D.fmt_ts(int(df["ts"].iloc[warm])), "to": D.fmt_ts(int(df["ts"].iloc[-1])),
              "split_at": D.fmt_ts(int(df["ts"].iloc[split])), "fee_pct": cfg["fee_pct"],
              "slippage_pct": cfg["slippage_pct"], "params": dict(strategy.params), "optimized": False}
    st = strategy
    if do_optimize:
        best, _ = optimize(strategy, df, cfg, warm, split, tf)
        result["optimized"] = True
        result["params"] = best
        st = strategy.with_params(best)
    sig = st.signals(df)
    result["full"], trades, equity, decisions = run_range(st, sig, cfg, warm, n, tf, collect=True)
    result["train"], *_ = run_range(st, sig, cfg, warm, split, tf)
    result["test"], *_ = run_range(st, sig, cfg, split, n, tf)
    if walk_forward:
        result["walk_forward"] = walk_forward_test(strategy, df, cfg, tf, warm, walk_forward)
    result["beats_hold_on_test"] = result["test"]["return_pct"] > result["test"]["hold_return_pct"]
    result["profitable_on_test"] = result["test"]["return_pct"] > 0
    if save:
        _save(result, trades, equity, decisions, df.iloc[warm:].reset_index(drop=True))
    return result


def walk_forward_test(strategy, df, cfg, tf, warm, folds):
    """Split the period into folds+1 equal windows. For each fold: optimise on the window
    before it, test on the window itself. Only test windows count."""
    n = len(df)
    edges = [warm + (n - warm) * k // (folds + 1) for k in range(folds + 2)]
    out = []
    for k in range(1, folds + 1):
        tr0, tr1, te1 = edges[k - 1], edges[k], edges[k + 1]
        best, _ = optimize(strategy, df, cfg, tr0, tr1, tf)
        st = strategy.with_params(best)
        m, *_ = run_range(st, st.signals(df), cfg, tr1, te1, tf)
        out.append({"test_from": D.fmt_ts(int(df["ts"].iloc[tr1])), "test_to": D.fmt_ts(int(df["ts"].iloc[te1 - 1])),
                    "params": best, "return_pct": m["return_pct"], "hold_return_pct": m["hold_return_pct"],
                    "trades": m["trades"], "max_dd_pct": m["max_dd_pct"]})
    comp = 1.0
    hold = 1.0
    for f in out:
        comp *= 1 + f["return_pct"] / 100
        hold *= 1 + f["hold_return_pct"] / 100
    return {"folds": out, "compounded_return_pct": (comp - 1) * 100, "compounded_hold_pct": (hold - 1) * 100}


def _save(result, trades, equity, decisions, dfw):
    RESULTS_DIR.mkdir(exist_ok=True)
    stem = f"bt_{result['strategy']}_{result['tf']}_{result['days']}d" + ("_opt" if result["optimized"] else "")
    (RESULTS_DIR / f"{stem}.json").write_text(json.dumps(result, indent=2, default=float), encoding="utf-8")
    t = pd.DataFrame(trades)
    if len(t):
        t["time"] = pd.to_datetime(t["ts"], unit="ms", utc=True)
    t.to_csv(RESULTS_DIR / f"{stem}_trades.csv", index=False)
    pd.DataFrame(decisions).assign(time=lambda d: pd.to_datetime(d["ts"], unit="ms", utc=True) if len(d) else None)         .to_csv(RESULTS_DIR / f"{stem}_decisions.csv", index=False)
    try:
        from .plot import equity_png
        equity_png(dfw["time"], equity, dfw["close"], RESULTS_DIR / f"{stem}.png",
                   f"{result['strategy']} {result['tf']} {result['days']}d vs holding BTC",
                   split_time=pd.Timestamp(result["split_at"].replace(" UTC", ""), tz="UTC"))
    except Exception as e:  # a chart failure must never lose the numbers
        print(f"[chart] skipped: {e}")


def fmt_row(r, seg):
    m = r[seg]
    return (f"| {r['strategy']} | {r['tf']} | {seg} | {m['return_pct']:+.1f}% | {m['hold_return_pct']:+.1f}% | "
            f"{m['max_dd_pct']:.1f}% | {m['win_rate_pct']:.0f}% | {m['trades']} | {m['sharpe']:.2f} | "
            f"{m['exposure_pct']:.0f}% | {m['fees_paid']:.0f} |")


TABLE_HEAD = ("| strategy | tf | period | return | hold BTC | max DD | win rate | trades | Sharpe | time in market | fees (USDT) |\n"
              "|---|---|---|---|---|---|---|---|---|---|---|")
