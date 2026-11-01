import math

import numpy as np
import pandas as pd

from .config import tf_minutes


def liquidation_value(cash, qty, price, fee_pct, slippage_pct):
    """What an account is worth if any open BTC is sold right now at `price`, paying slippage and the
    fee. Every return in this kit (strategies AND the hold-BTC benchmark) uses this, so they compare fairly."""
    return float(cash) + float(qty) * float(price) * (1 - slippage_pct / 100) * (1 - fee_pct / 100)


def max_drawdown(equity):
    e = pd.Series(equity, dtype=float)
    peak = e.cummax()
    return float(((e / peak) - 1).min() * 100) if len(e) else 0.0


def _bars_per_year(tf):
    return 365 * 24 * 60 / tf_minutes(tf)    # crypto trades 24/7


def sharpe(equity, tf):
    e = pd.Series(equity, dtype=float)
    r = e.pct_change().dropna()
    if len(r) < 2 or r.std() == 0:
        return 0.0
    return float(r.mean() / r.std() * math.sqrt(_bars_per_year(tf)))


def sortino(equity, tf):
    """Like Sharpe, but only downside moves count as risk (target return 0)."""
    e = pd.Series(equity, dtype=float)
    r = e.pct_change().dropna()
    if len(r) < 2:
        return 0.0
    downside = np.sqrt(np.mean(np.minimum(r.values, 0.0) ** 2))
    if downside == 0:
        return 0.0
    return float(r.mean() / downside * math.sqrt(_bars_per_year(tf)))


def monthly_returns(times, equity, start_balance):
    """{'YYYY-MM': % return in that calendar month (UTC)}; the first month is measured from the start balance."""
    if not len(equity):
        return {}
    s = pd.Series(list(equity), index=pd.to_datetime(list(times), unit="ms", utc=True)
                  if not isinstance(times[0], (pd.Timestamp, str)) else pd.to_datetime(list(times), utc=True), dtype=float)
    month_end = s.groupby(s.index.strftime("%Y-%m")).last()
    out, prev = {}, float(start_balance)
    for m, v in month_end.items():
        out[m] = (v / prev - 1) * 100 if prev else 0.0
        prev = v
    return out


def trade_stats(trades):
    """Profit factor, expectancy, average win/loss and fee drag over CLOSED trades (SELL rows carry the pnl).
    pnl is net of both fees; gross P&L = pnl + both fees of that trade."""
    sells = [t for t in trades if t.get("side") == "SELL" and t.get("pnl") is not None]
    wins = [t["pnl"] for t in sells if t["pnl"] > 0]
    losses = [t["pnl"] for t in sells if t["pnl"] <= 0]
    gross_win, gross_loss = sum(wins), -sum(losses)
    # fees of closed trades: each SELL's fee plus the matching BUY's fee (BUY rows have pnl None)
    buy_fee = {}
    for t in trades:
        if t.get("side") == "BUY":
            buy_fee[t.get("trade_id")] = t.get("fee") or 0.0
    closed_fees = sum((t.get("fee") or 0.0) + buy_fee.get(t.get("trade_id"), 0.0) for t in sells)
    net = sum(t["pnl"] for t in sells)
    gross = net + closed_fees
    n = len(sells)
    return {
        "trades": n,
        "win_rate_pct": (len(wins) / n * 100) if n else 0.0,
        "profit_factor": (gross_win / gross_loss) if gross_loss > 0 else (float("inf") if gross_win > 0 else 0.0),
        "expectancy_usdt": (net / n) if n else 0.0,
        "avg_win_usdt": (sum(wins) / len(wins)) if wins else 0.0,
        "avg_loss_usdt": (sum(losses) / len(losses)) if losses else 0.0,
        "gross_pnl_usdt": gross,
        "net_pnl_usdt": net,
        "closed_fees_usdt": closed_fees,
        # fees as a % of the gross (before-fee) P&L of closed trades. >100% means fees ate more than the edge.
        "fees_pct_of_gross": (closed_fees / abs(gross) * 100) if abs(gross) > 1e-9 else None,
    }


def summarize(equity, trades, tf, start_balance, closes, fee_pct, slippage_pct, in_market_bars=None,
              end_cash=None, end_qty=0.0, times=None):
    """Metrics for one simulated period. The final value is the LIQUIDATION value: an open position is
    counted as sold at the last close with slippage + fee, exactly like the hold-BTC benchmark."""
    end_mtm = equity[-1] if len(equity) else start_balance
    if end_cash is not None and end_qty and len(closes):
        end = liquidation_value(end_cash, end_qty, closes[-1], fee_pct, slippage_pct)
    else:
        end = end_mtm
    # buy & hold: buy at the first open with the same fee + slippage, sell at the last close with the same costs
    c0, c1 = closes[0], closes[-1]
    hold_qty = start_balance / (1 + fee_pct / 100) / (c0 * (1 + slippage_pct / 100))
    hold_curve = hold_qty * np.asarray(closes)
    hold_end = liquidation_value(0.0, hold_qty, c1, fee_pct, slippage_pct)
    ts = trade_stats(trades)
    ret = (end / start_balance - 1) * 100
    hold_ret = (hold_end / start_balance - 1) * 100
    out = {
        "return_pct": ret,
        "hold_return_pct": hold_ret,
        "excess_vs_hold_pct": ret - hold_ret,
        "max_dd_pct": max_drawdown(equity),
        "hold_max_dd_pct": max_drawdown(hold_curve),
        "trades": ts["trades"],
        "win_rate_pct": ts["win_rate_pct"],
        "profit_factor": ts["profit_factor"],
        "expectancy_usdt": ts["expectancy_usdt"],
        "avg_win_usdt": ts["avg_win_usdt"],
        "avg_loss_usdt": ts["avg_loss_usdt"],
        "fees_pct_of_gross": ts["fees_pct_of_gross"],
        "sharpe": sharpe(equity, tf),
        "sortino": sortino(equity, tf),
        "hold_sharpe": sharpe(hold_curve, tf),
        "fees_paid": sum(t["fee"] for t in trades),
        "exposure_pct": (in_market_bars / len(equity) * 100) if in_market_bars is not None and len(equity) else None,
        "end_equity": end,
        "end_equity_mark_to_market": end_mtm,
        "open_position_liquidated": bool(end_qty),
    }
    if times is not None and len(times) == len(equity):
        out["monthly_returns_pct"] = monthly_returns(times, equity[:-1] + [end] if len(equity) else equity, start_balance)
        out["hold_monthly_returns_pct"] = monthly_returns(
            times, list(hold_curve[:-1]) + [hold_end], start_balance)
    return out
