"""`python -m btcpaper report`: daily summary of a paper run (equity PNG, PnL, open position, decisions)."""
import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd

from . import data as D
from .config import RUNS_DIR
from .money import money, inr_group


def runs():
    return sorted(d for d in RUNS_DIR.iterdir() if d.is_dir() and (d / "state.json").exists() and "_archived_" not in d.name) \
        if RUNS_DIR.exists() else []


def report(cfg, run_name=None, date=None, inr=False, live_price=True):
    targets = [RUNS_DIR / run_name] if run_name else runs()
    if not targets:
        print("No paper runs yet. Start one with: python -m btcpaper paper --strategy ema_cross")
        return []
    tz = ZoneInfo(cfg.get("timezone", "UTC"))
    inr_rate = D.usdt_inr(cfg["usd_inr_fallback"])[0] if inr else None
    outs = []
    for rd in targets:
        if not (rd / "state.json").exists():
            print(f"no state.json in {rd}")
            continue
        meta = json.loads((rd / "state.json").read_text(encoding="utf-8"))
        s = meta["engine"]
        day = date or datetime.now(tz).strftime("%Y-%m-%d")
        rep_dir = rd / "reports"
        rep_dir.mkdir(exist_ok=True)

        def read(name):
            f = rd / name
            if not f.exists():
                return pd.DataFrame()
            df = pd.read_csv(f)
            if len(df):
                df["local"] = pd.to_datetime(df["ts"], unit="ms", utc=True).dt.tz_convert(tz)
                df["day"] = df["local"].dt.strftime("%Y-%m-%d")
            return df

        eq, tr, dec = read("equity.csv"), read("trades.csv"), read("decisions.csv")
        price = None
        if live_price:
            price, _ = D.last_price(cfg["symbol"], [meta.get("source")] + cfg["sources"] if meta.get("source") else cfg["sources"])
        price = price or s.get("last_close") or 0
        # liquidation value: an open position counts as sold now (fee + slippage), same rule as hold BTC
        from .metrics import liquidation_value
        equity = liquidation_value(s["cash"], s["qty"], price, meta.get("fee_pct", cfg["fee_pct"]),
                                   meta.get("slippage_pct", cfg["slippage_pct"]))
        start = s["start_balance"]
        eq_day = eq[eq["day"] == day] if len(eq) else eq
        prev = eq[eq["day"] < day] if len(eq) else eq
        day_open = float(prev["equity"].iloc[-1]) if len(prev) else (float(eq_day["equity"].iloc[0]) if len(eq_day) else start)
        sells = tr[tr["side"] == "SELL"] if len(tr) else tr
        sells_day = sells[sells["day"] == day] if len(sells) else sells
        wins = int((sells["pnl"] > 0).sum()) if len(sells) else 0

        png = rep_dir / f"equity_{day}.png"
        if len(eq) >= 2:
            from .plot import equity_png
            equity_png(pd.to_datetime(eq["ts"], unit="ms", utc=True), eq["equity"].values, eq["price"].values, png,
                       f"PAPER {meta['strategy']} {meta['tf']}: equity vs holding BTC", start_balance=start)
        else:
            png = None

        def pct(x):
            return f"{0.0 if abs(x) < 0.005 else x:+.2f}%"

        def cell(x):
            return str(x).replace("|", "/")

        tzname = cfg.get("timezone", "UTC")
        lines = [f"# Paper trading report: {meta['strategy']} on {meta['tf']} ({day})", "",
                 "PAPER MODE. Simulated money, real public prices.", "",
                 f"- Started: {meta.get('started')} with {money(start, inr_rate)}",
                 f"- BTC price now: {price:,.2f} USDT" + (f" (~Rs {inr_group(price * inr_rate)})" if inr_rate else ""),
                 f"- Equity now: {money(equity, inr_rate)}",
                 f"- Total PnL: {money(equity - start, inr_rate, sign=True)} ({pct((equity / start - 1) * 100)})",
                 f"- Today's PnL: {money(equity - day_open, inr_rate, sign=True)} ({pct((equity / day_open - 1) * 100)})",
                 f"- Fees paid so far: {s['fees_paid']:,.2f} USDT",
                 f"- Closed trades: {len(sells)} total, {len(sells_day)} today, win rate {(wins / len(sells) * 100) if len(sells) else 0:.0f}%",
                 ]
        if s["qty"] > 0:
            unreal = s["qty"] * price - s["entry_cost"] - s["entry_fee"]
            lines.append(f"- Open position: LONG {s['qty']:.6f} BTC from {s['entry_price']:,.2f}, stop {s['stop']:,.2f}, "
                         f"unrealised {money(unreal, inr_rate, sign=True)} | why: {s['entry_reason']}")
        else:
            lines.append("- Open position: none (flat)")
        if s.get("pending"):
            lines.append(f"- Pending order: {s['pending']['side'].upper()} at the next candle open")
        if s.get("halted_day"):
            lines.append(f"- HALTED on {s['halted_day']}: daily loss limit hit, trading resumes tomorrow")
        if png:
            lines += ["", f"![equity]({png.name})"]
        lines += ["", f"## Trades today ({len(tr[tr['day'] == day]) if len(tr) else 0})", ""]
        if len(tr) and len(tr[tr["day"] == day]):
            lines += [f"| time ({tzname}) | side | price | qty | fee | pnl | reason |", "|---|---|---|---|---|---|---|"]
            for _, r in tr[tr["day"] == day].iterrows():
                pnl = "" if pd.isna(r["pnl"]) else f"{r['pnl']:+.2f}"
                lines.append(f"| {r['local']:%H:%M} | {r['side']} | {r['price']:,.2f} | {r['qty']:.6f} | {r['fee']:.2f} | {pnl} | {cell(r['reason'])} |")
        else:
            lines.append("No trades today.")
        dday = dec[dec["day"] == day] if len(dec) else dec
        lines += ["", f"## Every decision today ({len(dday)} candles)", ""]
        if len(dday):
            counts = dday["action"].value_counts().to_dict()
            lines.append("Summary: " + ", ".join(f"{k} x{v}" for k, v in counts.items()))
            lines += ["", f"| time ({tzname}) | action | price | equity | reason |", "|---|---|---|---|---|"]
            for _, r in dday.iterrows():
                lines.append(f"| {r['local']:%H:%M} | {r['action']} | {r['price']:,.2f} | {r['equity']:,.2f} | {cell(r['reason'])} |")
        md = rep_dir / f"report_{day}.md"
        md.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print("\n".join(lines[:14]))
        print(f"\nFull report: {md}" + (f"\nEquity chart: {png}" if png else ""))
        outs.append(md)
    return outs
