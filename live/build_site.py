#!/usr/bin/env python3
"""Builds the dashboard data from the committed paper-account files.

  python live/build_site.py            -> _site/ (docs/ + data/summary.json), what GitHub Pages serves
Nothing here touches the network except for the current BTC price (if not passed in).
"""
import csv
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from btcpaper.metrics import liquidation_value, monthly_returns, sortino, trade_stats  # noqa: E402

LIVE = ROOT / "live"
STALE_MINUTES = 45      # the dashboard turns red when the last good tick is older than this
STATE = LIVE / "state"


def _j(p, d=None):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception:
        return d


def _csv(p):
    if not Path(p).exists():
        return []
    with open(p, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _f(x, d=None):
    try:
        return float(x)
    except (TypeError, ValueError):
        return d


def _close_time(dec, tfm):
    """decisions.csv stamps the candle's OPEN time; the decision is made when it closes."""
    try:
        ts = int(float(dec["ts"])) + tfm * 60_000
        return datetime.fromtimestamp(ts / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return dec.get("time")


def _thin(points, n=1500):
    if len(points) <= n:
        return points
    step = len(points) / n
    out = [points[int(i * step)] for i in range(n)]
    out[-1] = points[-1]
    return out


def _num(pat, s):
    import re
    m = re.search(pat, s or "")
    return float(m.group(1)) if m else None


def plain_reason(acc, dec, in_pos, params):
    """The decision in everyday words (the raw reason stays in decisions.csv)."""
    r, act = dec.get("reason", ""), dec.get("action", "")
    if act not in ("WAIT", "HOLD"):
        return r
    sid = acc.get("strategy")
    money = lambda v: f"${v:,.0f}"
    if sid == "ema_cross":
        import re
        m = re.search(r"ema(\d+)=([\d.]+) ema(\d+)=([\d.]+) trend=([\d.]+)", r)
        if m:
            f, fv, s, sv, tv = int(m.group(1)), float(m.group(2)), int(m.group(3)), float(m.group(4)), float(m.group(5))
            if in_pos:
                return f"Holding. Sells when the {f}h average ({money(fv)}) drops below the {s}h average ({money(sv)}), or at the stop."
            if fv < sv:
                return (f"Waiting. The {f}h average ({money(fv)}) is below the {s}h average ({money(sv)}). "
                        f"Buys when it crosses above, if price is over the 200h trend ({money(tv)}).")
            return (f"Waiting. The {f}h average is already above the {s}h one; it only buys on a fresh cross "
                    f"with price over the 200h trend ({money(tv)}).")
    if sid == "rsi_meanrev":
        rsi = _num(r"rsi=([\d.]+)", r)
        if rsi is not None:
            if in_pos:
                return f"Holding. RSI is {rsi:.0f}; sells when it gets back to {params.get('exit_rsi', 50)}, or at the stop."
            return f"Waiting for a dip. RSI is {rsi:.0f}; it buys when RSI falls below {params.get('low', 30)}."
    if sid == "donchian_breakout":
        hi, lo = _num(r"hi\d+=([\d.]+)", r), _num(r"lo\d+=([\d.]+)", r)
        if hi and lo:
            if in_pos:
                return f"Holding. Sells if price falls below the {params.get('exit_n', 20)}h low ({money(lo)}), or at the stop."
            return f"Waiting for a breakout above the {params.get('entry_n', 100)}h high ({money(hi)})."
    return r


def health(ticks, now=None):
    """Bot health from live/ticks.csv: last good tick, how many ticks in a row failed, minutes since good."""
    now = now or datetime.now(timezone.utc)
    last_ok = next((t for t in reversed(ticks) if t.get("status") == "ok"), None)
    fails = 0
    for t in reversed(ticks):
        if t.get("status") == "ok":
            break
        fails += 1
    mins = None
    if last_ok:
        lt = datetime.strptime(last_ok["time_utc"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        mins = round((now - lt).total_seconds() / 60, 1)
    return {"last_ok_tick_utc": last_ok["time_utc"] if last_ok else None,
            "consecutive_failures": fails,
            "minutes_since_ok": mins,
            "last_status": ticks[-1]["status"] if ticks else None,
            "stale_after_minutes": STALE_MINUTES,
            "stale": (mins is None) or mins > STALE_MINUTES}


def build_latest(price=None):
    acc_cfg = _j(LIVE / "accounts.json", {})
    meta = _j(LIVE / "meta.json", {})
    ticks = _csv(LIVE / "ticks.csv")
    last_tick = ticks[-1] if ticks else {}
    last_ok = next((t for t in reversed(ticks) if t.get("btc_price")), {})
    if price is None:
        price = _f(last_ok.get("btc_price"))
    rate = meta.get("inr_per_usdt_at_start") or 88.0
    fee, slip = meta.get("fee_pct", 0.1), meta.get("slippage_pct", 0.05)
    haircut = 1 - (1 - slip / 100) * (1 - fee / 100)      # cost of selling an open position right now
    start_usdt = meta.get("start_usdt") or 0
    accounts, trades, series = [], [], {}
    tfm = {"15m": 15, "30m": 30, "1h": 60, "4h": 240, "1d": 1440}.get(acc_cfg.get("timeframe", "1h"), 60)
    for a in acc_cfg.get("accounts", []):
        d = STATE / a["id"]
        st = _j(d / "state.json")
        if not st:
            accounts.append({"id": a["id"], "label": a["label"], "why": a.get("why", ""), "strategy": a["strategy"],
                             "params": a.get("params", {}), "started": None, "equity_usdt": start_usdt,
                             "equity_inr": start_usdt * rate, "pnl_pct": 0.0, "position": None,
                             "last_action": None, "trades": 0, "halted": False, "pending": None, "metrics": {}})
            continue
        e = st["engine"]
        px = price or e.get("last_close") or 0
        # liquidation value: any open BTC counts as sold now with fee + slippage (same rule for HOLD)
        eq = liquidation_value(e["cash"], e["qty"], px, fee, slip)
        start = e.get("start_balance") or start_usdt
        decs = _csv(d / "decisions.csv")
        tr = _csv(d / "trades.csv")
        last_trade = tr[-1] if tr else None
        last_dec = decs[-1] if decs else None
        pos = None
        if e["qty"] > 0:
            pos = {"btc": e["qty"], "entry": e.get("entry_price"), "stop": e.get("stop"),
                   "value_usdt": e["qty"] * px,
                   "unrealized_pct": (px / e["entry_price"] - 1) * 100 if e.get("entry_price") else None}
        accounts.append({
            "id": a["id"], "label": a["label"], "why": a.get("why", ""), "strategy": a["strategy"],
            "params": st.get("params", a.get("params", {})), "started": st.get("started"),
            "equity_usdt": eq, "equity_inr": eq * rate, "pnl_pct": (eq / start - 1) * 100 if start else 0,
            "cash_usdt": e["cash"], "fees_usdt": e.get("fees_paid", 0), "realized_usdt": e.get("realized_pnl", 0),
            "position": pos, "pending": (e.get("pending") or {}).get("side"),
            "halted": bool(e.get("halted_day")), "trades": len(tr),
            "last_trade": ({"time": last_trade["time"], "side": last_trade["side"],
                            "price": _f(last_trade["price"]), "reason": last_trade["reason"]} if last_trade else None),
            "last_action": ({"time": _close_time(last_dec, 0 if a["strategy"] == "HOLD" else tfm), "action": last_dec["action"], "price": _f(last_dec["price"]),
                             "reason": last_dec["reason"],
                             "plain": plain_reason(a, last_dec, e["qty"] > 0, st.get("params", a.get("params", {})))}
                            if last_dec else None),
            "decisions": len(decs),
        })
        for t in tr:
            trades.append({"time": t["time"], "account": a["label"], "id": a["id"], "side": t["side"],
                           "price": _f(t["price"]), "qty": _f(t["qty"]), "value": _f(t["value"]),
                           "fee": _f(t["fee"]), "pnl": _f(t.get("pnl")), "return_pct": _f(t.get("return_pct")),
                           "reason": t["reason"]})
        eq_rows = _csv(d / "equity.csv")
        liq = [_f(r["equity"], 0) - _f(r.get("position_btc"), 0) * _f(r.get("price"), 0) * haircut for r in eq_rows]
        pts = [[r["time"], round(v, 2)] for r, v in zip(eq_rows, liq)]
        series[a["id"]] = _thin(pts)
        tstats = trade_stats([{"side": t["side"], "pnl": _f(t.get("pnl")), "fee": _f(t.get("fee"), 0),
                               "trade_id": t.get("trade_id")} for t in tr])
        curve = [start] + liq + [eq]
        accounts[-1]["metrics"] = {
            "profit_factor": None if tstats["profit_factor"] == float("inf") else tstats["profit_factor"],
            "profit_factor_inf": tstats["profit_factor"] == float("inf"),
            "closed_trades": tstats["trades"], "win_rate_pct": tstats["win_rate_pct"],
            "expectancy_usdt": tstats["expectancy_usdt"], "avg_win_usdt": tstats["avg_win_usdt"],
            "avg_loss_usdt": tstats["avg_loss_usdt"], "fees_pct_of_gross": tstats["fees_pct_of_gross"],
            "fees_usdt": e.get("fees_paid", 0),
            "sortino": sortino(curve, acc_cfg.get("timeframe", "1h")) if len(curve) > 3 else None,
            "monthly_returns_pct": monthly_returns(
                [r["time"] for r in eq_rows] + [datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")],
                liq + [eq], start),
        }
    hold = next((x for x in accounts if x["strategy"] == "HOLD"), None)
    for x in accounts:
        x["excess_vs_hold_pct"] = (x["pnl_pct"] - hold["pnl_pct"]) if hold and x is not hold else None
    trades.sort(key=lambda t: t["time"], reverse=True)
    return {
        "mode": "PAPER TRADING - virtual money only",
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        "last_tick": last_tick, "recent_ticks": ticks[-12:][::-1],
        "ticks_ok_24h": sum(1 for t in ticks[-96:] if t.get("status") == "ok"),
        "ticks_24h": len(ticks[-96:]),
        "btc_price": price, "price_source": last_ok.get("source"),
        "inr_per_usdt": rate, "meta": meta, "timeframe": acc_cfg.get("timeframe"),
        "health": health(ticks),
        "valuation": "liquidation: open BTC counted as sold now with fee + slippage, same for every account",
        "accounts": accounts, "recent_trades": trades[:40], "trade_count": len(trades),
        "equity_series": series,
    }


def main():
    out = ROOT / "_site"
    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(ROOT / "docs", out)
    (out / "data").mkdir(exist_ok=True)
    latest = build_latest()
    (out / "data" / "summary.json").write_text(json.dumps(latest, ensure_ascii=False), encoding="utf-8")
    (out / ".nojekyll").write_text("")
    print(f"[site] built {out} ({len(latest['accounts'])} accounts, {latest['trade_count']} trades)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
