#!/usr/bin/env python3
"""V2 research: multi-regime, walk-forward, out-of-sample test of BTC strategies vs HOLD and weekly DCA.

  python research/v2_regimes.py            (needs data/hist_BTCUSDT_1h.csv; fetches it if missing)

Protocol (nothing here is tuned on the periods it is judged on):
  * Data: BTC/USDT 1h candles from June 2020 (Binance public data); 4h = the same candles resampled.
  * Walk-forward, anchored: for each test year Y in 2022..2026, parameters are tuned (grid search, best
    Sortino with a minimum trade count) on 2021-01-01 .. Y-01-01 ONLY, then run on year Y. The yearly
    test pieces are chained into one out-of-sample (OOS) equity curve from 2022-01-01 to now.
  * Every regime number below is read from that OOS curve. 2021 is training data only.
  * Costs everywhere: 0.1% fee + 0.05% slippage per side; fills at the next candle's open; any position
    still open at the end of a window is counted as sold (same rule for HOLD and DCA).
  * An "edge" claim needs >= 30 closed trades out-of-sample.
Writes RESULTS_V2.md and docs/v2.json.
"""
import itertools
import json
import math
import sys
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from btcpaper import data as D                       # noqa: E402
from btcpaper.backtest import run_range              # noqa: E402
from btcpaper.config import DEFAULTS, tf_minutes     # noqa: E402
from btcpaper.metrics import max_drawdown, sortino   # noqa: E402
from btcpaper.strategies import load                 # noqa: E402

HIST = ROOT / "data" / "hist_BTCUSDT_1h.csv"
FEE, SLIP = DEFAULTS["fee_pct"], DEFAULTS["slippage_pct"]
START = 10_000.0
ALLOC = {"risk_per_trade_pct": 100.0, "max_position_pct": 100.0, "daily_loss_limit_pct": 100.0}
TEST_YEARS = [2022, 2023, 2024, 2025, 2026]
TRAIN_FROM = "2021-01-01"


def ms(s):
    return int(pd.Timestamp(s, tz="UTC").timestamp() * 1000)


REGIMES = [
    ("bear22", "2022 bear", "2022-01-01", "2023-01-01"),
    ("bull2324", "2023-24 bull", "2023-01-01", "2025-01-01"),
    ("chop25", "2025 chop/range", "2025-01-01", "2026-01-01"),
    ("last6m", "Last 6 months", "2026-05-01", None),
    ("oos", "All out-of-sample (2022 to now)", "2022-01-01", None),
]

CANDIDATES = [
    # id, label, strategy file, timeframe, risk config, min train trades
    ("trend_sma200d", "Trend filter (daily SMA, tuned 100-200d)", "trend_sma200d", "4h", ALLOC, 2),
    ("tsmom", "Time-series momentum (3 or 6 mo)", "tsmom", "4h", ALLOC, 2),
    ("macd_regime", "MACD + 200D trend filter (4h)", "macd_regime", "4h", {}, 10),
    ("bb_squeeze", "Bollinger squeeze breakout (4h)", "bb_squeeze", "4h", {}, 10),
    ("vol_target", "Volatility-targeted hold", None, "4h", None, 0),
    ("ema_cross", "EMA crossover (live #1)", "ema_cross", "1h", {}, 10),
    ("rsi_meanrev", "RSI dip-buyer (live #2)", "rsi_meanrev", "1h", {}, 3),
    ("donchian_breakout", "Donchian breakout (live #3)", "donchian_breakout", "1h", {}, 10),
]
VOL_GRID = {"target": [0.3, 0.5], "lookback_days": [20, 60]}


# ---------------------------------------------------------------- data
def load_data():
    if not HIST.exists():
        HIST.parent.mkdir(exist_ok=True)
        df, _ = D.fetch("BTC/USDT", "1h", ms("2020-06-01"), None, ["binance_vision", "okx", "bitstamp"], verbose=True)
        df.to_csv(HIST, index=False)
    df = pd.read_csv(HIST)
    df["time"] = pd.to_datetime(df["ts"], unit="ms", utc=True)
    return df


def resample(df1h, rule="4h"):
    g = df1h.set_index("time").resample(rule, label="left", closed="left")
    out = pd.DataFrame({"open": g["open"].first(), "high": g["high"].max(), "low": g["low"].min(),
                        "close": g["close"].last(), "volume": g["volume"].sum()}).dropna()
    n_per = int(pd.Timedelta(rule) / pd.Timedelta("1h"))
    counts = df1h.set_index("time")["close"].resample(rule, label="left", closed="left").count()
    out = out[counts.reindex(out.index) == n_per]          # complete candles only
    out = out.reset_index()
    out["ts"] = ((out["time"] - pd.Timestamp("1970-01-01", tz="UTC")) // pd.Timedelta(milliseconds=1)).astype("int64")
    return out[["ts", "open", "high", "low", "close", "volume", "time"]]


def idx_at(df, when_ms):
    return int(np.searchsorted(df["ts"].values, when_ms, side="left"))


# ---------------------------------------------------------------- simulators
def cfg_for(extra):
    c = dict(DEFAULTS)
    c.update(extra or {})
    return c


def engine_run(strat, sig, cfg, i0, i1, tf):
    m, trades, equity, _ = run_range(strat, sig, cfg, i0, i1, tf)
    return m, trades, equity


def exposure_run(df, weights, i0, i1, band=0.1, start=START):
    """Target-exposure simulator: weights[i] (0..1) decided at the close of candle i, traded at the open of
    candle i+1 when it differs from the current exposure by more than `band`. Fee + slippage on every trade."""
    O, C, TS = df["open"].values, df["close"].values, df["ts"].values
    cash, qty, w_target = start, 0.0, None
    eq, trades = [], []
    for i in range(i0, i1):
        if w_target is not None and not math.isnan(w_target):
            o = O[i]
            val = cash + qty * o
            cur = qty * o / val if val > 0 else 0.0
            if abs(w_target - cur) > band or (w_target == 0 and qty > 0) or (w_target >= 0.999 and cur < 0.95):
                want = w_target * val / o
                dq = want - qty
                if dq > 0:
                    px = o * (1 + SLIP / 100)
                    dq = min(dq, cash / (px * (1 + FEE / 100)))
                    cost = dq * px
                    cash -= cost * (1 + FEE / 100)
                    qty += dq
                    trades.append({"ts": int(TS[i]), "side": "BUY", "fee": cost * FEE / 100, "pnl": None})
                elif dq < 0:
                    px = o * (1 - SLIP / 100)
                    proceeds = -dq * px
                    cash += proceeds * (1 - FEE / 100)
                    qty += dq
                    trades.append({"ts": int(TS[i]), "side": "SELL", "fee": proceeds * FEE / 100, "pnl": 0.0})
        eq.append(cash + qty * C[i])
        w_target = weights[i]
    end_liq = cash + qty * C[i1 - 1] * (1 - SLIP / 100) * (1 - FEE / 100)
    return eq, trades, end_liq


def vol_weights(df, target, lookback_days):
    """min(1, target / realized annual vol of completed daily closes)."""
    day = df["time"].dt.floor("D")
    dclose = df["close"].groupby(day).last()
    vol = np.log(dclose).diff().rolling(lookback_days, min_periods=lookback_days).std() * math.sqrt(365)
    w = (target / vol).clip(upper=1.0).shift(1)                 # yesterday's completed vol only
    return pd.Series(day.map(w).values, index=df.index, dtype=float).values


def hold_curve(df, i0, i1, start=START):
    o0 = df["open"].values[i0]
    qty = start / (1 + FEE / 100) / (o0 * (1 + SLIP / 100))
    eq = list(qty * df["close"].values[i0:i1])
    end_liq = qty * df["close"].values[i1 - 1] * (1 - SLIP / 100) * (1 - FEE / 100)
    return eq, end_liq


def dca_curve(df, i0, i1, start=START):
    """Weekly DCA: the money is split evenly over every Monday-00:00-UTC candle in the window."""
    t = df["time"].iloc[i0:i1]
    buys = [i0 + k for k, (d, h) in enumerate(zip(t.dt.weekday, t.dt.hour)) if d == 0 and h == 0]
    if not buys:
        return hold_curve(df, i0, i1, start)
    per = start / len(buys)
    O, C = df["open"].values, df["close"].values
    cash, qty, eq, bset = start, 0.0, [], set(buys)
    for i in range(i0, i1):
        if i in bset:
            spend = min(per, cash)
            qty += spend / (1 + FEE / 100) / (O[i] * (1 + SLIP / 100))
            cash -= spend
        eq.append(cash + qty * C[i])
    end_liq = cash + qty * C[i1 - 1] * (1 - SLIP / 100) * (1 - FEE / 100)
    return eq, end_liq


# ---------------------------------------------------------------- walk-forward
def grid_of(strat):
    if not strat.grid:
        return [{}]
    keys = list(strat.grid)
    return [dict(zip(keys, combo)) for combo in itertools.product(*[strat.grid[k] for k in keys])]


def _score(eq, n_trades, min_trades, tf):
    if n_trades < min_trades:
        return -1e9 + n_trades
    return sortino(eq, tf)


def walk_forward(cand, frames):
    cid, label, sname, tf, risk, min_tr = cand
    df = frames[tf]
    folds, chain_ts, chain_eq, chain_trades = [], [], [], []
    value = START
    first = idx_at(df, ms(f"{TEST_YEARS[0]}-01-01"))
    chain_ts.append(int(df["ts"].values[first - 1]))
    chain_eq.append(START)
    tr0 = idx_at(df, ms(TRAIN_FROM))
    for y in TEST_YEARS:
        te0 = idx_at(df, ms(f"{y}-01-01"))
        te1 = idx_at(df, ms(f"{y + 1}-01-01")) if y < TEST_YEARS[-1] else len(df)
        if te1 - te0 < 10:
            continue
        # ---- tune on TRAIN only
        best, best_s = None, -1e18
        if sname is None:   # volatility target
            for combo in itertools.product(*VOL_GRID.values()):
                p = dict(zip(VOL_GRID, combo))
                w = vol_weights(df, p["target"], p["lookback_days"])
                eq, tr, _ = exposure_run(df, w, tr0, te0)
                s = _score(eq, len(tr), min_tr, tf)
                if s > best_s:
                    best, best_s = p, s
            w = vol_weights(df, best["target"], best["lookback_days"])
            eq, trades, end_liq = exposure_run(df, w, te0, te1)
        else:
            base = load(sname)
            cfg = cfg_for(risk)
            for p in grid_of(base):
                st = base.with_params(p)
                m, tr, eq = engine_run(st, st.signals(df), cfg, tr0, te0, tf)
                s = _score(eq, m["trades"], min_tr, tf)
                if s > best_s:
                    best, best_s = p, s
            st = base.with_params(best)
            m, trades, eq = engine_run(st, st.signals(df), cfg, te0, te1, tf)
            end_liq = m["end_equity"]
        # ---- chain the TEST piece
        scale = value / START
        ts = df["ts"].values[te0:te1]
        chain_ts += [int(x) for x in ts]
        chain_eq += [v * scale for v in eq[:-1]] + [end_liq * scale]
        for t in trades:
            chain_trades.append({"ts": int(t["ts"]), "side": t["side"], "fee": float(t.get("fee") or 0) * scale,
                                 "pnl": (None if t.get("pnl") is None else float(t["pnl"]) * scale)})
        folds.append({"test_year": y, "params": best, "return_pct": (end_liq / START - 1) * 100,
                      "trades": sum(1 for t in trades if t["side"] == "SELL")})
        value = end_liq * scale
    return {"id": cid, "label": label, "tf": tf, "folds": folds,
            "ts": chain_ts, "eq": chain_eq, "trades": chain_trades}


# ---------------------------------------------------------------- metrics per window
def window_metrics(ts, eq, trades, a_ms, b_ms, tf):
    ts, eq = np.asarray(ts), np.asarray(eq, dtype=float)
    j0 = int(np.searchsorted(ts, a_ms, side="left"))
    j1 = int(np.searchsorted(ts, b_ms, side="left")) if b_ms else len(ts)
    if j1 - j0 < 2:
        return None
    base = eq[j0 - 1] if j0 > 0 else eq[j0]
    seg = np.r_[base, eq[j0:j1]]
    ret = seg[-1] / seg[0] - 1
    days = (ts[j1 - 1] - (ts[j0 - 1] if j0 > 0 else ts[j0])) / 86_400_000
    cagr = (1 + ret) ** (365 / days) - 1 if days > 0 and ret > -1 else -1.0
    dd = max_drawdown(seg)
    sells = [t for t in trades if t["side"] == "SELL" and a_ms <= t["ts"] < (b_ms or 1 << 62)]
    wins = [t["pnl"] for t in sells if t["pnl"] is not None and t["pnl"] > 0]
    losses = [t["pnl"] for t in sells if t["pnl"] is not None and t["pnl"] <= 0]
    fees = sum(t["fee"] for t in trades if a_ms <= t["ts"] < (b_ms or 1 << 62))
    return {"return_pct": ret * 100, "cagr_pct": cagr * 100, "max_dd_pct": dd,
            "sortino": sortino(seg, tf), "calmar": (cagr * 100 / abs(dd)) if dd < 0 else None,
            "trades": len(sells),
            "profit_factor": (sum(wins) / -sum(losses)) if losses and sum(losses) < 0 else None,
            "win_rate_pct": (len(wins) / len(sells) * 100) if sells else None,
            "fees_pct_of_start": fees / seg[0] * 100}


def bench_window(df, a_ms, b_ms, kind, tf):
    i0 = idx_at(df, a_ms)
    i1 = idx_at(df, b_ms) if b_ms else len(df)
    eq, end_liq = (hold_curve if kind == "hold" else dca_curve)(df, i0, i1)
    eq = eq[:-1] + [end_liq]
    ts = list(df["ts"].values[i0:i1])
    ts = [int(df["ts"].values[i0 - 1])] + [int(x) for x in ts]
    eq = [START] + eq
    trades = [{"ts": ts[1], "side": "BUY", "fee": START * FEE / 100, "pnl": None}]
    return window_metrics(ts, eq, trades, a_ms, b_ms, tf)


def _wf(args):
    cand, frames = args
    return walk_forward(cand, frames)


def main():
    df1 = load_data()
    frames = {"1h": df1, "4h": resample(df1, "4h")}
    last = df1["time"].iloc[-1]
    with ProcessPoolExecutor(max_workers=min(8, len(CANDIDATES))) as ex:
        results = list(ex.map(_wf, [(c, frames) for c in CANDIDATES]))
    table = {}
    for r in results:
        table[r["id"]] = {w[0]: window_metrics(r["ts"], r["eq"], r["trades"], ms(w[2]), ms(w[3]) if w[3] else None, r["tf"])
                          for w in REGIMES}
    bench = {}
    for kind in ("hold", "dca"):
        bench[kind] = {w[0]: bench_window(frames["4h"], ms(w[2]), ms(w[3]) if w[3] else None, kind, "4h")
                       for w in REGIMES}
    hold_oos = bench["hold"]["oos"]
    verdicts = []
    for r in results:
        o = table[r["id"]]["oos"]
        reasons = []
        if o["trades"] < 30:
            reasons.append(f"only {o['trades']} closed trades out-of-sample (< 30): no edge claim possible")
        if o["sortino"] <= hold_oos["sortino"]:
            reasons.append(f"Sortino {o['sortino']:.2f} <= HOLD {hold_oos['sortino']:.2f}")
        if (o["calmar"] or -9) <= (hold_oos["calmar"] or -9):
            reasons.append(f"Calmar {o['calmar'] or 0:.2f} <= HOLD {hold_oos['calmar'] or 0:.2f}")
        if o["return_pct"] <= 0:
            reasons.append("lost money out-of-sample")
        verdicts.append({"id": r["id"], "label": r["label"], "tf": r["tf"], "pass": not reasons,
                         "reasons": reasons, "excess_vs_hold_pct": o["return_pct"] - hold_oos["return_pct"],
                         "folds": r["folds"]})
    # risk-adjusted rank: Calmar, then Sortino (out-of-sample only)
    order = sorted(results, key=lambda r: ((table[r["id"]]["oos"]["calmar"] or -99), table[r["id"]]["oos"]["sortino"]),
                   reverse=True)
    rank = {r["id"]: k + 1 for k, r in enumerate(order)}
    for v in verdicts:
        v["rank"] = rank[v["id"]]
    verdicts.sort(key=lambda v: v["rank"])
    # thin OOS curves for the web page (daily points)
    curves = {}
    for r in results + [{"id": "hold", "tf": "4h"}]:
        if r["id"] == "hold":
            i0 = idx_at(frames["4h"], ms("2022-01-01"))
            eq, liq = hold_curve(frames["4h"], i0, len(frames["4h"]))
            ts, eq = list(frames["4h"]["ts"].values[i0:]), eq[:-1] + [liq]
        else:
            ts, eq = r["ts"], r["eq"]
        s = pd.Series(eq, index=pd.to_datetime(ts, unit="ms", utc=True)).resample("W").last().dropna()
        curves[r["id"]] = [[d.strftime("%Y-%m-%d"), round(v / START * 100, 2)] for d, v in s.items()]
    out = {"generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"),
           "data_to": last.strftime("%Y-%m-%d %H:%M UTC"), "regimes": REGIMES, "table": table, "bench": bench,
           "verdicts": verdicts, "curves": curves, "fee_pct": FEE, "slippage_pct": SLIP,
           "labels": {c[0]: c[1] for c in CANDIDATES}}
    (ROOT / "docs").mkdir(exist_ok=True)
    (ROOT / "docs" / "v2.json").write_text(json.dumps(out, default=float), encoding="utf-8")
    (ROOT / "RESULTS_V2.md").write_text(render_md(out), encoding="utf-8")
    print(render_md(out))


def _f(v, fmt="{:+.1f}%"):
    return "n/a" if v is None else fmt.format(v)


def render_md(o):
    L = [f"# V2 results: strategies vs HOLD across market regimes (out-of-sample)", "",
         f"Data: BTC/USDT, Binance public candles, to {o['data_to']}. Generated {o['generated_utc']} UTC by `research/v2_regimes.py`.",
         f"Costs: {o['fee_pct']}% fee + {o['slippage_pct']}% slippage per side, next-candle-open fills, open positions counted as sold at the end (same for HOLD and DCA).",
         "Protocol: anchored walk-forward. Each test year (2022, 2023, 2024, 2025, 2026 so far) uses parameters tuned only on data before it (from 2021). "
         "The test years are chained into one out-of-sample curve; every number below comes from it. An \"edge\" needs at least 30 closed trades.",
         "PASS rule (all out-of-sample, 2022 to now): at least 30 closed trades, Sortino AND Calmar better than HOLD, and a positive return.", ""]
    for key, name, a, b in o["regimes"]:
        L.append(f"## {name} ({a} to {b or 'now'})")
        L.append("")
        L.append("| strategy | return | vs HOLD | max DD | Sortino | Calmar | closed trades | win rate | profit factor | fees (% of start) |")
        L.append("|---|---|---|---|---|---|---|---|---|---|")
        hold = o["bench"]["hold"][key]
        rows = [(o["labels"][k], v[key]) for k, v in o["table"].items()] + \
               [("HOLD (lump sum)", hold), ("Weekly DCA", o["bench"]["dca"][key])]
        rows.sort(key=lambda r: -(r[1]["return_pct"] if r[1] else -999))
        for nm, m in rows:
            if not m:
                continue
            L.append(f"| {nm} | {_f(m['return_pct'])} | {_f(m['return_pct'] - hold['return_pct'])} | {m['max_dd_pct']:.1f}% | "
                     f"{m['sortino']:.2f} | {_f(m['calmar'], '{:.2f}')} | {m['trades']} | {_f(m['win_rate_pct'], '{:.0f}%')} | "
                     f"{_f(m['profit_factor'], '{:.2f}')} | {m['fees_pct_of_start']:.1f}% |")
        L.append("")
    L.append("## Ranking (risk-adjusted, out-of-sample: Calmar, then Sortino) and verdicts")
    L.append("")
    for v in o["verdicts"]:
        m = o["table"][v["id"]]["oos"]
        L.append(f"{v['rank']}. **{v['label']}** ({v['tf']}): {'PASS' if v['pass'] else 'FAIL'}. "
                 f"OOS {m['return_pct']:+.1f}% ({v['excess_vs_hold_pct']:+.1f} pts vs HOLD), max DD {m['max_dd_pct']:.1f}%, "
                 f"Sortino {m['sortino']:.2f}, Calmar {_f(m['calmar'], '{:.2f}')}, {m['trades']} trades."
                 + ("" if v["pass"] else " Why: " + "; ".join(v["reasons"]) + "."))
        L.append("   Params chosen per test year (tuned on earlier data only): " +
                 ", ".join(f"{f['test_year']}: {f['params'] or 'fixed'}" for f in v["folds"]))
    h = o["bench"]["hold"]["oos"]
    d = o["bench"]["dca"]["oos"]
    L += ["", f"HOLD (2022 to now): {h['return_pct']:+.1f}%, max DD {h['max_dd_pct']:.1f}%, Sortino {h['sortino']:.2f}, Calmar {_f(h['calmar'], '{:.2f}')}.",
          f"Weekly DCA (2022 to now, money spread evenly over every week): {d['return_pct']:+.1f}%, max DD {d['max_dd_pct']:.1f}%, Sortino {d['sortino']:.2f}.",
          "", "## Weak spots",
          "- One asset, one exchange's prices, about 4.8 years out-of-sample. A few big BTC moves dominate every number.",
          "- The candidates are well-known ideas chosen with hindsight (people already know trend filters worked on BTC). That selection is a bias no walk-forward can remove.",
          "- Small grids were tuned per year; with 5 test years, luck still matters. Trend and momentum trade rarely: they only just clear the 30-trade bar, so their edge is thin evidence, not proof.",
          "- Fees/slippage are modelled at 0.1% + 0.05% per side. Real slippage in fast markets can be worse; Indian taxes (30% + 1% TDS) are not included.",
          "- Survivorship: BTC is the asset that survived; the same rules on coins that died would look very different.",
          "- Risk sizing: MACD, Bollinger and the original 3 use the live risk rules (1% risk per trade, max 50% in a trade), so they are often only partly invested. Trend and momentum hold a full position when in."]
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    main()
