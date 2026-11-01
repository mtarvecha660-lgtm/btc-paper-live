# Strategy guide

A strategy is one Python file in `strategies/`. The loader picks up every `*.py` there except files starting with `_`.
Start from `strategies/_template.py`.

## The format

```python
from btcpaper.indicators import ema, atr, crossed_above

NAME = "my_idea"                      # must match the file name (my_idea.py)
DESCRIPTION = "one line in plain English"
PARAMS = {"n": 50, "atr_period": 14, "atr_mult": 2.0}     # defaults
GRID = {"n": [20, 50, 100], "atr_mult": [1.5, 2.5]}       # optional: what --optimize may try (keep it small)

def compute(df, p):
    out = df.copy()
    out["ma"] = ema(out["close"], p["n"])
    out["atr"] = atr(out, p["atr_period"])
    out["enter"] = crossed_above(out["close"], out["ma"])     # bool: buy at the NEXT candle's open
    out["exit"] = out["close"] < out["ma"]                    # bool: sell at the NEXT candle's open
    out["stop"] = out["close"] - p["atr_mult"] * out["atr"]   # stop-loss price for an entry on this row
    out["note"] = "ma=" + out["ma"].round(0).astype(str)      # optional: shown in the decision log
    return out
```

`df` holds CLOSED candles only, oldest first: `ts` (ms, candle open time, UTC), `time`, `open`, `high`, `low`, `close`, `volume`.

| column | required | meaning |
|---|---|---|
| `enter` | yes | True = buy at the next candle's open (only when flat) |
| `exit` | yes | True = sell at the next candle's open (only when holding) |
| `stop` | yes | absolute stop-loss price for an entry signalled on this row; must be below `close`, otherwise the entry is skipped |
| `trail_stop` | no | while holding, the stop is raised to this value if higher (never lowered) |
| `note` | no | text written to the decision log, e.g. the indicator values or why it fired |

Indicators available in `btcpaper.indicators`: `ema`, `sma`, `rsi`, `atr`, `donchian`, `crossed_above`, `crossed_below`.
Any pandas that only looks backwards is fine: `rolling(n)`, `ewm(...)`, `expanding()`, `shift(1)`, `diff()`.

## What the engine does for you (don't re-implement it)
- Fills at the next candle's open with slippage (default 0.05%) and a fee (default 0.1%) on both sides.
- Checks the stop on every candle's low. If price gaps below the stop, it fills at the open (worse), like real life.
- Position size: risk `risk_per_trade_pct` (1%) of equity to the stop, capped at `max_position_pct` (50%) of equity and at the cash available. No leverage, long only.
- Daily loss limit: if equity falls `daily_loss_limit_pct` (3%) below where the day started (Indian time), it closes the position and takes no new trades until the next day.

## Look-ahead: the one mistake that makes a backtest lie
Row `i` may only use rows `0..i`. These all leak the future and are rejected:

| don't | why | instead |
|---|---|---|
| `x.shift(-1)` | next candle's value | `x.shift(1)` (previous) |
| `rolling(n, center=True)` | half the window is in the future | `rolling(n)` |
| `bfill()` / `fillna(method="bfill")` | copies future values back | `ffill()` |
| `df["close"].max()` / `.mean()` over the whole column | uses the whole dataset | `rolling(n).max()` / `expanding().max()` |
| `df.iloc[i + 1]`, `df.iloc[-1]` inside compute | future row / last row of all data | vectorised columns |
| normalising with full-period stats, fitting a model on all rows | the fit has seen the test period | rolling or expanding fits |

`python -m btcpaper check` runs two tests: a scan for the patterns above, and the real one: it computes your signals on the full history, then again with the data cut off at 40 points, and fails if any past signal changes when future candles are added. That catches hidden leaks the scan can't see.

## Judging a strategy
- Only the TEST period counts (the last 30% of the backtest). Parameters tuned with `--optimize` only ever see the train part.
- Beat buy-and-hold on the test period, after fees, and make money there. "Lost less than holding" in a falling market is cash, not skill.
- Fewer than ~20 test trades = luck can't be ruled out. `--walk-forward 3` is the tougher check: tune on one window, test on the next, three times.
- Look at fees paid. Frequent trading on 15m candles often hands most of the edge to the exchange.
- Max drawdown is the pain you'll actually feel. Compare it with holding's drawdown.
