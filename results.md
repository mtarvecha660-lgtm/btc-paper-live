# Backtest results (real data, run on 2026-11-01 08:34 UTC)

BTC/USDT, last 180 days (2026-05-05 08:30 UTC to 2026-11-01 08:15 UTC). Candles: Binance public data (served by its data mirror; the main Binance API refused this test machine's location with HTTP 451, and the kit fell back automatically).
Costs: 0.1% fee + 0.05% slippage on every buy and sell. Fills at the next candle's open. Risk: 1% of equity per trade to the stop, max 50% of equity in a trade, 3% daily loss limit, long only, no leverage.
Train = first 70%, test = last 30% (test starts 2026-09-08 08:30 UTC). 'hold BTC' = buy at the start, sell at the end, same costs.

## 1. Default parameters (nothing tuned), test period = the only fair column

| strategy | tf | test return | hold BTC (test) | test max DD | hold max DD (test) | test trades | test win rate | test Sharpe | full 180d return | hold 180d | full max DD | hold max DD | fees 180d (USDT) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ema_cross | 15m | -3.7% | -0.9% | -8.8% | -12.3% | 32 | 19% | -2.55 | -9.8% | -3.7% | -14.4% | -29.6% | 916 |
| rsi_meanrev | 15m | -1.2% | -0.9% | -1.2% | -12.3% | 4 | 0% | -5.32 | -2.9% | -3.7% | -2.9% | -29.6% | 138 |
| donchian_breakout | 15m | -5.9% | -0.9% | -6.6% | -12.3% | 44 | 18% | -4.75 | -21.2% | -3.7% | -21.3% | -29.6% | 1328 |
| ema_cross | 1h | -6.5% | -0.8% | -6.5% | -12.1% | 9 | 0% | -6.90 | -13.2% | -3.8% | -14.0% | -29.4% | 234 |
| rsi_meanrev | 1h | -0.9% | -0.8% | -1.0% | -12.1% | 1 | 0% | -2.79 | +1.1% | -3.8% | -1.0% | -29.4% | 51 |
| donchian_breakout | 1h | -1.1% | -0.8% | -5.0% | -12.1% | 10 | 40% | -1.03 | -2.4% | -3.8% | -8.6% | -29.4% | 345 |

## 2. Tuned on train only (--optimize), then judged on test + walk-forward (3 folds)

| strategy | tf | chosen params | test return | hold BTC (test) | test trades | walk-forward return | walk-forward hold |
|---|---|---|---|---|---|---|---|
| ema_cross | 15m | {fast: 30, slow: 100, atr_mult: 2.0} | -8.4% | -0.9% | 25 | -5.3% | +23.1% |
| rsi_meanrev | 15m | {low: 30, exit_rsi: 50, atr_mult: 2.5} | -0.7% | -0.9% | 4 | -3.3% | +23.1% |
| donchian_breakout | 15m | {entry_n: 100, exit_n: 20, atr_mult: 3.0} | -2.3% | -0.9% | 30 | -10.5% | +23.1% |
| ema_cross | 1h | {fast: 20, slow: 100, atr_mult: 2.0} | -0.1% | -0.8% | 9 | +2.2% | +23.4% |
| rsi_meanrev | 1h | {low: 35, exit_rsi: 50, atr_mult: 2.5} | -0.6% | -0.8% | 2 | +0.9% | +23.4% |
| donchian_breakout | 1h | {entry_n: 100, exit_n: 10, atr_mult: 2.0} | -1.4% | -0.8% | 8 | +4.1% | +23.4% |

## Verdict (honest)
- **Nothing beats just holding BTC in a way that counts.** With default parameters, all 6 strategy/timeframe combos did worse than holding BTC on the test period after fees.
- After tuning on the train part, three combos "beat" holding on the test period, but only by losing less while sitting mostly in cash (all three test returns are negative), and on just 2 to 9 test trades. That's not evidence of an edge.
- Walk-forward is the toughest test. BTC rose about 23% over the three test windows. The best strategy made +4% (Donchian 1h); the 15m versions lost 3% to 11%.
- 15m trading is the worst: Donchian 15m paid about 1,300 USDT in fees on a 10,000 account in 180 days, and fees and slippage alone explain most of its loss.
- The one real plus: drawdowns are much smaller than holding, because the strategies are in the market only 1% to 30% of the time with a stop on every trade. Lower risk, lower return.
- Period caveat: this is one 6-month stretch (BTC ended about 4% down, but fell almost 30% from its high along the way). Other periods will give different numbers.

Raw files: `results/summary_*.md`, `results/bt_*.json` (all metrics), `bt_*_trades.csv`, `bt_*_decisions.csv`, `bt_*.png` (equity vs hold).
