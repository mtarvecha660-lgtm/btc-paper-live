"""Live PAPER trading loop. Public candles in, simulated fills out. No keys, no real orders.

State lives in runs/<strategy>_<tf>/:
  state.json      balances, open position, pending order (restart resumes from here)
  trades.csv      trade journal (every simulated BUY/SELL with fee, PnL and reason)
  decisions.csv   one row per closed candle: what the bot decided and why
  equity.csv      equity after every candle
"""
import csv
import json
import os
import signal
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from . import data as D
from .config import RUNS_DIR, tf_minutes
from .engine import Engine, new_state
from .money import money

TRADE_COLS = ["time", "trade_id", "side", "price", "qty", "value", "fee", "pnl", "return_pct", "stop", "reason",
              "entry_price", "entry_time", "ts"]
DEC_COLS = ["time", "action", "price", "equity", "reason", "ts"]
EQ_COLS = ["time", "equity", "price", "position_btc", "ts"]


def run_dir(strategy_name, tf):
    d = RUNS_DIR / f"{strategy_name}_{tf}"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _iso(ms):
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def save_state(path, state):
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2), encoding="utf-8")
    for attempt in range(10):       # atomic replace: a crash or Ctrl+C never leaves half a file
        try:
            os.replace(tmp, path)
            return
        except PermissionError:     # Windows: OneDrive / antivirus can hold the file for a moment
            time.sleep(0.3)
    os.replace(tmp, path)


def _append(path, cols, row):
    for attempt in range(5):
        try:
            new = not path.exists()
            with open(path, "a", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
                if new:
                    w.writeheader()
                w.writerow(row)
            return
        except PermissionError:      # Windows: the CSV is open in Excel (Excel locks it)
            time.sleep(0.5)
    side = path.with_name(path.stem + "_while_locked.csv")
    print(f"[paper] WARNING: {path.name} is locked (open in Excel?). Close it. Row written to {side.name} instead.")
    new = not side.exists()
    with open(side, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        if new:
            w.writeheader()
        w.writerow(row)


def _log_trade(rd, ev):
    row = dict(ev)
    row["time"] = _iso(ev["ts"])
    if ev.get("entry_ts"):
        row["entry_time"] = _iso(ev["entry_ts"])
    _append(rd / "trades.csv", TRADE_COLS, row)
    print(f"  >> {row['time']} UTC  PAPER {ev['side']} {ev['qty']:.6f} BTC @ {ev['price']:.2f} "
          f"fee {ev['fee']:.2f}" + (f" pnl {ev['pnl']:+.2f}" if ev['pnl'] is not None else "")
          + f" | {ev['reason'][:90]}", flush=True)


def paper(strategy, cfg, tf, balance=None, inr=False, minutes=None, once=False, reset=False, max_catchup_days=7):
    step = tf_minutes(tf) * 60_000
    rd = run_dir(strategy.name, tf)
    sp = rd / "state.json"
    if reset and sp.exists():
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        archive = rd.parent / f"{rd.name}_archived_{stamp}"
        rd.rename(archive)
        rd = run_dir(strategy.name, tf)
        sp = rd / "state.json"
        print(f"[paper] old run moved to {archive.name}")

    inr_rate = None
    if inr or cfg.get("show_inr"):
        inr_rate, inr_src = D.usdt_inr(cfg["usd_inr_fallback"])
        print(f"[paper] 1 USDT = Rs {inr_rate:.2f} ({inr_src})")

    if sp.exists():
        st = json.loads(sp.read_text(encoding="utf-8"))
        state = st["engine"]
        if st.get("params") != strategy.params:
            print(f"[paper] note: strategy params changed since this run started ({st.get('params')} -> {strategy.params})")
        print(f"[paper] resuming {rd.name}: equity {money(state['cash'] + state['qty'] * (state['last_close'] or 0), inr_rate)}"
              + (f", last candle {_iso(state['last_ts'])} UTC" if state["last_ts"] else ""))
        meta = st
    else:
        bal = balance or cfg["starting_balance_usdt"]
        state = new_state(bal)
        meta = {"strategy": strategy.name, "tf": tf, "params": strategy.params, "symbol": cfg["symbol"],
                "started": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "fee_pct": cfg["fee_pct"], "slippage_pct": cfg["slippage_pct"], "mode": "PAPER"}
        print(f"[paper] new paper account: {money(bal, inr_rate)} virtual, strategy {strategy.name} on {tf}")
    eng = Engine(cfg, state)

    def persist():
        meta["engine"] = eng.s
        meta["updated"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        save_state(sp, meta)

    persist()
    deadline = time.time() + minutes * 60 if minutes else None
    stop_flag = {"stop": False}

    def _sig(*_):
        stop_flag["stop"] = True
        raise KeyboardInterrupt
    try:
        signal.signal(signal.SIGTERM, _sig)
    except Exception:
        pass

    print("[paper] PAPER MODE: simulated money only. Ctrl+C stops safely; run the same command to resume.")
    last_fetch_err = None
    try:
        while True:
            now = int(time.time() * 1000)
            last = eng.s["last_ts"]
            newest_closed = ((now - 3000) // step) * step - step  # latest fully closed candle (3 s grace for the exchange)
            if last is None or newest_closed > last:
                try:
                    warm = cfg["warmup_bars"]
                    since = newest_closed - (warm + 5) * step
                    if last is not None:
                        since = min(since, last - warm * step)
                        since = max(since, now - (max_catchup_days * 86_400_000) - warm * step)
                    df, src = D.fetch(cfg["symbol"], tf, since, now + step, cfg["sources"], verbose=False,
                                      use_cache=False, keep_forming=True)
                    last_fetch_err = None
                    forming = None
                    if len(df) and int(df["ts"].iloc[-1]) + step > int(time.time() * 1000):
                        forming = df.iloc[-1]                 # still-open candle: only its OPEN price is used
                        df = df.iloc[:-1].reset_index(drop=True)
                except Exception as e:
                    df = None
                    msg = str(e).splitlines()[0][:160]
                    if msg != last_fetch_err:
                        print(f"[paper] data fetch failed ({msg}); retrying in {cfg['poll_seconds']}s")
                    last_fetch_err = msg
                if df is not None and len(df):
                    if last is None:
                        # fresh start: do not replay history, start deciding from the latest closed candle
                        last = int(df["ts"].iloc[-2])
                        eng.s["last_ts"] = last
                    elif last < int(df["ts"].iloc[0]):
                        # offline longer than the catch-up window: don't replay a week+ of history blind
                        print(f"[paper] offline longer than {max_catchup_days} days; skipping ahead, pending order cancelled")
                        eng.s["pending"] = None
                        last = int(df["ts"].iloc[min(warm, len(df) - 2)])
                        eng.s["last_ts"] = last
                    todo = df.index[df["ts"] > last].tolist()
                    if len(todo) > 1:
                        print(f"[paper] catching up {len(todo)} closed candles (source: {src})")
                    for i in todo:
                        window = df.iloc[: i + 1].reset_index(drop=True)
                        sig = strategy.signals(window).iloc[-1]
                        bar = df.iloc[i]
                        s = {"enter": bool(sig["enter"]), "exit": bool(sig["exit"]), "stop": float(sig["stop"]),
                             "trail_stop": float(sig["trail_stop"]) if "trail_stop" in sig.index else None,
                             "note": str(sig.get("note", ""))}
                        events, dec = eng.on_bar(bar, s)
                        if dec is None:
                            continue
                        for ev in events:
                            _log_trade(rd, ev)
                        _append(rd / "decisions.csv", DEC_COLS, {**dec, "time": _iso(dec["ts"]), "source": src})
                        print(f"  candle {_iso(dec['ts'])[11:16]} UTC closed @ {dec['price']:,.2f}: {dec['action']} | {dec['reason'][:110]}", flush=True)
                        _append(rd / "equity.csv", EQ_COLS, {"time": _iso(dec["ts"]), "equity": round(dec["equity"], 4),
                                                             "price": dec["price"], "position_btc": eng.s["qty"], "ts": dec["ts"]})
                        persist()
                    # the next candle has already opened: fill a pending order at its open right now
                    if forming is not None and eng.s["last_ts"] is not None and int(forming["ts"]) == eng.s["last_ts"] + step:
                        evs, _ = eng.on_open(int(forming["ts"]), float(forming["open"]))
                        for ev in evs:
                            _log_trade(rd, ev)
                        persist()
                    meta["source"] = src
                    cfg = {**cfg, "sources": [src] + [x for x in cfg["sources"] if x != src]}  # stick to what works
                    persist()
            _status(eng, tf, inr_rate, cfg)
            if once:
                break
            if deadline and time.time() >= deadline:
                print("[paper] time limit reached")
                break
            sleep_s = cfg["poll_seconds"]
            if deadline:
                sleep_s = max(1, min(sleep_s, deadline - time.time()))
            time.sleep(sleep_s)
    except KeyboardInterrupt:
        print("\n[paper] stopping...")
    finally:
        persist()
        print(f"[paper] state saved to {sp}. Run the same command to resume.")
    return rd


def _status(eng, tf, inr_rate, cfg):
    s = eng.s
    price, src = D.last_price(cfg["symbol"], cfg["sources"])
    price = price or s["last_close"] or 0
    eq = eng.equity(price)
    pnl = eq - s["start_balance"]
    day_pnl = eq - s["day_start_equity"]
    pos = (f"LONG {s['qty']:.6f} BTC @ {s['entry_price']:.2f} stop {s['stop']:.2f}" if s["qty"] > 0 else "FLAT")
    pend = f" | pending {s['pending']['side'].upper()} at next open" if s["pending"] else ""
    halt = " | HALTED for today (daily loss limit)" if s["halted_day"] else ""
    step = tf_minutes(tf) * 60
    nxt = step - (time.time() % step)
    line = (f"[{datetime.now().strftime('%H:%M:%S')}] BTC {price:,.2f} | equity {money(eq, inr_rate)} | "
            f"PnL {pnl / s['start_balance'] * 100:+.2f}% ({money(pnl, inr_rate, sign=True)}) | today {money(day_pnl, None, sign=True)} | "
            f"{pos}{pend}{halt} | next {tf} candle closes in {int(nxt // 60)}m{int(nxt % 60):02d}s")
    print(line, flush=True)
