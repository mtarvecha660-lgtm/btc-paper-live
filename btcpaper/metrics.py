import math

import numpy as np
import pandas as pd

from .config import tf_minutes


def max_drawdown(equity):
    e = pd.Series(equity, dtype=float)
    peak = e.cummax()
    return float(((e / peak) - 1).min() * 100) if len(e) else 0.0


def sharpe(equity, tf):
    e = pd.Series(equity, dtype=float)
    r = e.pct_change().dropna()
    if len(r) < 2 or r.std() == 0:
        return 0.0
    bars_per_year = 365 * 24 * 60 / tf_minutes(tf)   # crypto trades 24/7
    return float(r.mean() / r.std() * math.sqrt(bars_per_year))


def summarize(equity, trades, tf, start_balance, closes, fee_pct, slippage_pct, in_market_bars=None):
    sells = [t for t in trades if t["side"] == "SELL"]
    wins = [t for t in sells if t["pnl"] > 0]
    gross_win = sum(t["pnl"] for t in wins)
    gross_loss = -sum(t["pnl"] for t in sells if t["pnl"] <= 0)
    end = equity[-1] if len(equity) else start_balance
    # buy & hold: buy at the first open with the same fee + slippage, value at the last close (minus a sell fee)
    c0, c1 = closes[0], closes[-1]
    hold_qty = start_balance / (1 + fee_pct / 100) / (c0 * (1 + slippage_pct / 100))
    hold_curve = hold_qty * np.asarray(closes)
    hold_end = hold_curve[-1] * (1 - slippage_pct / 100) * (1 - fee_pct / 100)
    return {
        "return_pct": (end / start_balance - 1) * 100,
        "hold_return_pct": (hold_end / start_balance - 1) * 100,
        "max_dd_pct": max_drawdown(equity),
        "hold_max_dd_pct": max_drawdown(hold_curve),
        "trades": len(sells),
        "win_rate_pct": (len(wins) / len(sells) * 100) if sells else 0.0,
        "profit_factor": (gross_win / gross_loss) if gross_loss > 0 else (float("inf") if gross_win > 0 else 0.0),
        "sharpe": sharpe(equity, tf),
        "hold_sharpe": sharpe(hold_curve, tf),
        "fees_paid": sum(t["fee"] for t in trades),
        "exposure_pct": (in_market_bars / len(equity) * 100) if in_market_bars is not None and len(equity) else None,
        "end_equity": end,
    }
