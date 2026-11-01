"""python -m btcpaper <command>

  list                                   show strategies
  check [--strategy X]                   reject look-ahead / broken strategies
  backtest --strategy X|all --tf 15m --days 180 [--optimize] [--walk-forward 4]
  paper --strategy X [--tf 15m] [--balance 10000 | --balance-inr 900000] [--inr] [--minutes N] [--once] [--reset]
  report [--run ema_cross_15m] [--date YYYY-MM-DD] [--inr]
  test                                   run the unit tests
PAPER ONLY: nothing here can place a real order.
"""
import argparse
import sys
from datetime import datetime

try:  # Windows consoles: make sure Rs/emoji/odd characters never crash a print
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from .config import load_config, RESULTS_DIR


def _common(p):
    p.add_argument("--fee", type=float, help="fee %% per side (default 0.1)")
    p.add_argument("--slippage", type=float, help="slippage %% per side (default 0.05)")
    p.add_argument("--risk", type=float, help="%% of equity risked per trade (default 1)")
    p.add_argument("--max-position", type=float, help="max %% of equity in one trade (default 50)")
    p.add_argument("--daily-loss", type=float, help="daily loss limit %% (default 3)")
    p.add_argument("--param", action="append", metavar="KEY=VALUE", help="override a strategy parameter (repeatable)")


def _cfg(a):
    return load_config({"fee_pct": a.fee, "slippage_pct": a.slippage, "risk_per_trade_pct": a.risk,
                        "max_position_pct": a.max_position, "daily_loss_limit_pct": a.daily_loss})


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m btcpaper", description="Bitcoin PAPER trading kit (no real money).")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list", help="list strategies")

    c = sub.add_parser("check", help="reject strategies that look ahead")
    c.add_argument("--strategy", action="append")

    b = sub.add_parser("backtest", help="backtest with fees, slippage and a train/test split")
    b.add_argument("--strategy", default="all", help="strategy name or 'all'")
    b.add_argument("--tf", default="15m", help="timeframe(s), e.g. 15m or 15m,1h")
    b.add_argument("--days", type=int, default=180)
    b.add_argument("--optimize", action="store_true", help="tune params on the TRAIN part only, then judge on TEST")
    b.add_argument("--walk-forward", type=int, default=0, metavar="FOLDS", help="rolling optimise->test folds")
    b.add_argument("--balance", type=float)
    _common(b)

    pp = sub.add_parser("paper", help="run the live paper-trading loop")
    pp.add_argument("--strategy", required=True)
    pp.add_argument("--tf", default="15m")
    pp.add_argument("--balance", type=float, help="virtual starting balance in USDT (new runs only)")
    pp.add_argument("--balance-inr", type=float, help="virtual starting balance in rupees (converted to USDT)")
    pp.add_argument("--inr", action="store_true", help="also show rupee values")
    pp.add_argument("--minutes", type=float, help="stop automatically after N minutes")
    pp.add_argument("--once", action="store_true", help="process any new candles, print status, exit (for Task Scheduler)")
    pp.add_argument("--reset", action="store_true", help="archive the old run and start fresh")
    _common(pp)

    r = sub.add_parser("report", help="daily paper-trading report")
    r.add_argument("--run", help="run folder name, e.g. ema_cross_15m (default: all runs)")
    r.add_argument("--date", help="YYYY-MM-DD (default: today)")
    r.add_argument("--inr", action="store_true")

    sub.add_parser("test", help="run unit tests")

    a = ap.parse_args(argv)

    if a.cmd == "list":
        from .strategies import load_all
        for s in load_all():
            print(f"{s.name:20s} {s.description}\n{'':20s} params: {s.params}")
        return 0

    if a.cmd == "check":
        from .check import check
        ok, _ = check(a.strategy)
        print("ALL PASS" if ok else "SOME STRATEGIES FAILED: fix them before backtesting")
        return 0 if ok else 1

    if a.cmd == "test":
        import unittest
        from .config import ROOT
        suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"), top_level_dir=str(ROOT))
        res = unittest.TextTestRunner(verbosity=2).run(suite)
        return 0 if res.wasSuccessful() else 1

    if a.cmd == "backtest":
        from . import data as D
        from .backtest import backtest, fmt_row, TABLE_HEAD
        from .check import check
        from .strategies import load, load_all, parse_params
        cfg = _cfg(a)
        if a.balance:
            cfg["starting_balance_usdt"] = a.balance
        params = parse_params(a.param)
        strats = load_all() if a.strategy == "all" else [load(a.strategy, params)]
        ok, rep = check([s.path.stem for s in strats], verbose=False)
        for name, v in rep.items():
            if not v["ok"]:
                print(f"[check] {name} FAILED the look-ahead check: {v['static'] + v['dynamic']}")
        strats = [s for s in strats if rep.get(s.name, {"ok": True})["ok"]]
        if not strats:
            return 1
        results = []
        for tf in a.tf.split(","):
            tf = tf.strip()
            df, src = D.fetch_days(cfg["symbol"], tf, a.days, cfg["warmup_bars"], cfg["sources"])
            for s in strats:
                res = backtest(s, cfg, tf, a.days, a.optimize, a.walk_forward, df=df, source=src)
                results.append(res)
        lines = [f"Backtest {datetime.now():%Y-%m-%d %H:%M}, last {a.days} days, {cfg['symbol']}, "
                 f"fee {cfg['fee_pct']}%/side, slippage {cfg['slippage_pct']}%/side, risk {cfg['risk_per_trade_pct']}%/trade, "
                 f"max position {cfg['max_position_pct']}%, source {results[0]['source']}",
                 f"Train = first {cfg['train_pct']:.0f}%, test = last {100 - cfg['train_pct']:.0f}% (test starts {results[0]['split_at']})"
                 + (" | params tuned on TRAIN only" if a.optimize else " | default params, nothing tuned"), "",
                 TABLE_HEAD]
        for res in results:
            for seg in ("full", "train", "test"):
                lines.append(fmt_row(res, seg))
        lines.append("")
        for res in results:
            t = res["test"]
            if not res["beats_hold_on_test"]:
                verdict = "does NOT beat buy-and-hold on the test period"
            elif t["return_pct"] <= 0:
                verdict = "lost LESS than buy-and-hold on the test period (mostly by sitting in cash), but still lost money"
            else:
                verdict = "BEATS buy-and-hold on the test period"
            warn = (f" | only {t['trades']} test trade{'' if t['trades'] == 1 else 's'}: too few to trust"
                    if t["trades"] < 20 else "")
            lines.append(f"- {res['strategy']} {res['tf']}: {verdict} "
                         f"({t['return_pct']:+.1f}% vs {t['hold_return_pct']:+.1f}%){warn}"
                         + (f" | params {res['params']}" if res["optimized"] else ""))
            if res.get("walk_forward"):
                wf = res["walk_forward"]
                lines.append(f"  walk-forward ({len(wf['folds'])} folds, test windows only): "
                             f"{wf['compounded_return_pct']:+.1f}% vs hold {wf['compounded_hold_pct']:+.1f}%")
        text = "\n".join(lines)
        print("\n" + text)
        RESULTS_DIR.mkdir(exist_ok=True)
        out = RESULTS_DIR / f"summary_{datetime.now():%Y%m%d_%H%M%S}.md"
        out.write_text(text + "\n", encoding="utf-8")
        print(f"\nSaved: {out} (+ per-strategy json, trades csv, decisions csv and equity png in {RESULTS_DIR})")
        return 0

    if a.cmd == "paper":
        from . import data as D
        from .check import check
        from .paper import paper
        from .strategies import load, parse_params
        cfg = _cfg(a)
        st = load(a.strategy, parse_params(a.param))
        ok, rep = check([st.path.stem], verbose=False)
        if not ok:
            print(f"[check] {st.name} failed the look-ahead check, refusing to paper trade it: {rep}")
            return 1
        bal = a.balance
        if a.balance_inr:
            rate, src = D.usdt_inr(cfg["usd_inr_fallback"])
            bal = a.balance_inr / rate
            from .money import inr_group
            print(f"[paper] Rs {inr_group(a.balance_inr)} = {bal:,.2f} USDT at {rate:.2f} ({src})")
        paper(st, cfg, a.tf, balance=bal, inr=a.inr or bool(a.balance_inr), minutes=a.minutes, once=a.once, reset=a.reset)
        return 0

    if a.cmd == "report":
        from .report import report
        report(load_config(), a.run, a.date, a.inr)
        return 0


if __name__ == "__main__":
    sys.exit(main())
