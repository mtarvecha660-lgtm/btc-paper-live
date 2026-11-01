#!/usr/bin/env python3
"""One tick of the live PAPER bot. GitHub Actions runs this every ~15 minutes.

PAPER ONLY: public price data in, simulated fills out. There are no exchange keys
anywhere in this repo and no code path that can place a real order.

What one tick does:
  1. For each strategy account in live/accounts.json: process any 1h candles that
     closed since the last tick (decide, fill at the next candle's open with fees +
     slippage), using the same engine as the backtests (btcpaper/engine.py).
  2. The "Just Hold BTC" benchmark buys once with all its money on its first tick.
  3. Appends one line to live/ticks.csv (ok / skipped / error), then writes
     live/latest.json for the dashboard.
If every price source fails, the tick is logged as "skipped" and nothing else changes.
"""
import contextlib
import csv
import io
import json
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from btcpaper import data as D            # noqa: E402
from btcpaper import paper as P           # noqa: E402
from btcpaper.config import load_config   # noqa: E402
from btcpaper.strategies import load      # noqa: E402

LIVE = ROOT / "live"
STATE = LIVE / "state"
TICKS = LIVE / "ticks.csv"
TICK_COLS = ["time_utc", "status", "btc_price", "source", "note"]
MAX_TICK_ROWS = 600          # about 6 days of 15-minute ticks; older lines are trimmed


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def read_json(p, default=None):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception:
        return default


def write_json(p, obj):
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj, indent=1, ensure_ascii=False), encoding="utf-8")
    tmp.replace(p)


def append_csv(path, cols, row):
    new = not path.exists()
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        if new:
            w.writeheader()
        w.writerow(row)


def read_csv(path):
    if not Path(path).exists():
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def trim_csv(path, cols, keep):
    rows = read_csv(path)
    if len(rows) <= keep:
        return
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows[-keep:])


def account_dir(acc_id):
    d = STATE / acc_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def run_strategy(acc, cfg, tf, start_usdt):
    """Runs the kit's own paper loop once (paper --once) for one account. Returns (ok, note)."""
    strat = load(acc["strategy"], acc.get("params") or {})
    P.run_dir = lambda _name, _tf, _d=acc["id"]: account_dir(_d)   # one folder per account id
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        P.paper(strat, cfg, tf, balance=start_usdt, once=True)
    out = buf.getvalue()
    sys.stdout.write(f"--- {acc['id']} ---\n{out}")
    for line in out.splitlines():
        if "data fetch failed" in line:
            return False, line.strip()[:200]
    return True, ""


def run_hold(acc, cfg, start_usdt, price, src):
    """Benchmark: buy once with everything (same fee + slippage), then just mark to market."""
    d = account_dir(acc["id"])
    sp = d / "state.json"
    st = read_json(sp)
    if st is None:
        if not price:
            return False, "hold: no price yet, will buy next tick"
        fee, slip = cfg["fee_pct"] / 100, cfg["slippage_pct"] / 100
        fill = price * (1 + slip)
        value = start_usdt / (1 + fee)
        qty = value / fill
        ts = int(datetime.now(timezone.utc).timestamp() * 1000)
        eng = {"cash": 0.0, "qty": qty, "start_balance": start_usdt, "entry_price": fill, "entry_ts": ts,
               "stop": None, "pending": None, "halted_day": None, "last_ts": None, "fees_paid": value * fee,
               "realized_pnl": 0.0, "last_close": price, "trade_id": 1}
        st = {"strategy": "HOLD", "tf": "-", "params": {}, "mode": "PAPER", "started": now_iso(), "engine": eng}
        P._log_trade(d, {"trade_id": 1, "ts": ts, "side": "BUY", "price": fill, "qty": qty, "value": value,
                         "fee": value * fee, "pnl": None, "stop": None,
                         "reason": "Benchmark: buy BTC once with all the money and hold it, never sell"})
        append_csv(d / "decisions.csv", P.DEC_COLS, {"time": P._iso(ts), "action": "BUY", "price": fill,
                   "equity": start_usdt - value * fee, "ts": ts,
                   "reason": "Benchmark: bought once with all the money; it only holds from here"})
    eng = st["engine"]
    # one equity point per closed candle, using the closes the strategy accounts just recorded
    closes = {}
    for other in sorted(STATE.iterdir()):
        if other.name != acc["id"]:
            for r in read_csv(other / "equity.csv"):
                closes[int(r["ts"])] = float(r["price"])
    last = eng.get("last_ts") or eng["entry_ts"] - 1
    for ts in sorted(t for t in closes if t > last and t >= eng["entry_ts"]):
        px = closes[ts]
        P._append(d / "equity.csv", P.EQ_COLS, {"time": P._iso(ts), "equity": round(eng["cash"] + eng["qty"] * px, 4),
                                                 "price": px, "position_btc": eng["qty"], "ts": ts})
        eng["last_ts"], eng["last_close"] = ts, px
    st["updated"] = now_iso()
    write_json(sp, st)
    return True, ""


def main():
    acc_cfg = read_json(LIVE / "accounts.json")
    tf = acc_cfg.get("timeframe", "1h")
    cfg = load_config({})
    # GitHub's runners are in the US, where api.binance.com answers HTTP 451.
    # Binance's public data mirror answers there, so try it first; the rest are fallbacks.
    cfg["sources"] = ["binance_vision"] + [s for s in cfg["sources"] if s != "binance_vision"]
    STATE.mkdir(parents=True, exist_ok=True)

    meta = read_json(LIVE / "meta.json", {})
    if "start_usdt" not in meta:
        rate, rsrc = D.usdt_inr(cfg["usd_inr_fallback"])
        meta = {"mode": "PAPER (virtual money)", "started": now_iso(), "start_inr": acc_cfg["start_inr"],
                "inr_per_usdt_at_start": round(rate, 4), "inr_rate_source": rsrc,
                "start_usdt": round(acc_cfg["start_inr"] / rate, 4), "timeframe": tf,
                "fee_pct": cfg["fee_pct"], "slippage_pct": cfg["slippage_pct"],
                "risk_per_trade_pct": cfg["risk_per_trade_pct"], "max_position_pct": cfg["max_position_pct"],
                "daily_loss_limit_pct": cfg["daily_loss_limit_pct"]}
        write_json(LIVE / "meta.json", meta)

    price, psrc = D.last_price(cfg["symbol"], cfg["sources"])
    status, notes = ("ok" if price else "skipped"), ([] if price else ["no price source answered"])
    if price:
        for acc in acc_cfg["accounts"]:
            if acc["strategy"] == "HOLD":
                continue
            try:
                ok, note = run_strategy(acc, cfg, tf, meta["start_usdt"])
                if not ok:
                    status, notes = "skipped", notes + [f"{acc['id']}: {note}"]
            except BaseException as e:   # one broken strategy must not stop the others
                traceback.print_exc()
                status = "error"
                notes.append(f"{acc['id']}: {type(e).__name__}: {str(e)[:150]}")
        for acc in acc_cfg["accounts"]:
            if acc["strategy"] == "HOLD":
                try:
                    ok, note = run_hold(acc, cfg, meta["start_usdt"], price, psrc)
                    if not ok:
                        notes.append(note)
                except Exception as e:
                    traceback.print_exc()
                    status = "error"
                    notes.append(f"{acc['id']}: {type(e).__name__}: {str(e)[:150]}")

    append_csv(TICKS, TICK_COLS, {"time_utc": now_iso(), "status": status,
                                  "btc_price": round(price, 2) if price else "", "source": psrc or "",
                                  "note": " | ".join(notes)[:400]})
    trim_csv(TICKS, TICK_COLS, MAX_TICK_ROWS)

    from build_site import build_latest      # noqa: E402  (live/build_site.py)
    latest = build_latest(price)
    write_json(LIVE / "latest.json", {k: v for k, v in latest.items() if k != "equity_series"})
    print(f"[tick] {status} | BTC {price} ({psrc}) | " + " | ".join(
        f"{a['id']} {a['pnl_pct']:+.2f}%" for a in latest["accounts"]) + (f" | notes: {notes}" if notes else ""))
    # A skipped or errored tick exits non-zero so the GitHub run shows red. The workflow still commits
    # whatever succeeded and rebuilds the dashboard (those steps run `if: always()`).
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    sys.path.insert(0, str(LIVE))
    sys.exit(main())
