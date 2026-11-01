# V2 results: strategies vs HOLD across market regimes (out-of-sample)

Data: BTC/USDT, Binance public candles, to 2026-11-01 08:00 UTC. Generated 2026-11-01 09:48 UTC by `research/v2_regimes.py`.
Costs: 0.1% fee + 0.05% slippage per side, next-candle-open fills, open positions counted as sold at the end (same for HOLD and DCA).
Protocol: anchored walk-forward. Each test year (2022, 2023, 2024, 2025, 2026 so far) uses parameters tuned only on data before it (from 2021). The test years are chained into one out-of-sample curve; every number below comes from it. An "edge" needs at least 30 closed trades.
PASS rule (all out-of-sample, 2022 to now): at least 30 closed trades, Sortino AND Calmar better than HOLD, and a positive return.

## 2022 bear (2022-01-01 to 2023-01-01)

| strategy | return | vs HOLD | max DD | Sortino | Calmar | closed trades | win rate | profit factor | fees (% of start) |
|---|---|---|---|---|---|---|---|---|---|
| MACD + 200D trend filter (4h) | +0.0% | +64.3% | 0.0% | 0.00 | n/a | 0 | n/a | n/a | 0.0% |
| Bollinger squeeze breakout (4h) | -4.1% | +60.2% | -5.7% | -1.02 | -0.72 | 28 | 32% | 0.65 | 1.9% |
| RSI dip-buyer (live #2) | -8.2% | +56.2% | -8.2% | -3.04 | -1.00 | 19 | 21% | 0.26 | 1.8% |
| EMA crossover (live #1) | -8.6% | +55.7% | -15.1% | -1.11 | -0.57 | 32 | 22% | 0.61 | 2.9% |
| Donchian breakout (live #3) | -13.6% | +50.8% | -15.9% | -1.71 | -0.85 | 105 | 26% | 0.71 | 7.2% |
| Trend filter (daily SMA, tuned 100-200d) | -21.5% | +42.8% | -31.1% | -1.93 | -0.69 | 4 | 0% | 0.00 | 0.7% |
| Weekly DCA | -34.1% | +30.2% | -39.3% | -1.91 | -0.87 | 0 | n/a | n/a | 0.1% |
| Time-series momentum (3 or 6 mo) | -34.1% | +30.2% | -34.2% | -2.77 | -1.00 | 8 | 12% | 0.01 | 1.2% |
| Volatility-targeted hold | -57.0% | +7.4% | -59.8% | -2.07 | -0.95 | 4 | 0% | n/a | 0.2% |
| HOLD (lump sum) | -64.3% | +0.0% | -67.2% | -1.89 | -0.96 | 0 | n/a | n/a | 0.1% |

## 2023-24 bull (2023-01-01 to 2025-01-01)

| strategy | return | vs HOLD | max DD | Sortino | Calmar | closed trades | win rate | profit factor | fees (% of start) |
|---|---|---|---|---|---|---|---|---|---|
| HOLD (lump sum) | +464.0% | +0.0% | -30.0% | 3.06 | 4.57 | 0 | n/a | n/a | 0.1% |
| Volatility-targeted hold | +326.2% | -137.8% | -21.2% | 3.29 | 5.01 | 6 | 0% | n/a | 0.6% |
| Time-series momentum (3 or 6 mo) | +211.2% | -252.8% | -30.1% | 2.30 | 2.53 | 19 | 37% | 3.15 | 6.6% |
| Trend filter (daily SMA, tuned 100-200d) | +209.4% | -254.6% | -34.3% | 2.32 | 2.21 | 15 | 33% | 1.79 | 5.9% |
| Weekly DCA | +143.5% | -320.5% | -25.9% | 2.24 | 2.16 | 0 | n/a | n/a | 0.1% |
| Bollinger squeeze breakout (4h) | +39.0% | -425.0% | -8.0% | 3.36 | 2.24 | 57 | 40% | 2.42 | 5.7% |
| MACD + 200D trend filter (4h) | +24.7% | -439.3% | -13.4% | 1.70 | 0.87 | 131 | 34% | 1.36 | 11.3% |
| Donchian breakout (live #3) | +14.5% | -449.5% | -15.1% | 0.99 | 0.46 | 180 | 33% | 1.18 | 18.4% |
| EMA crossover (live #1) | +11.4% | -452.6% | -21.5% | 0.68 | 0.26 | 82 | 18% | 1.23 | 7.5% |
| RSI dip-buyer (live #2) | +0.9% | -463.1% | -1.3% | 0.59 | 0.34 | 6 | 50% | 1.60 | 0.6% |

## 2025 chop/range (2025-01-01 to 2026-01-01)

| strategy | return | vs HOLD | max DD | Sortino | Calmar | closed trades | win rate | profit factor | fees (% of start) |
|---|---|---|---|---|---|---|---|---|---|
| Time-series momentum (3 or 6 mo) | +15.2% | +21.8% | -14.2% | 0.92 | 1.07 | 3 | 67% | 4.95 | 0.6% |
| Trend filter (daily SMA, tuned 100-200d) | +5.2% | +11.8% | -17.7% | 0.45 | 0.29 | 10 | 30% | 1.39 | 2.1% |
| RSI dip-buyer (live #2) | +0.0% | +6.6% | 0.0% | 0.00 | n/a | 0 | n/a | n/a | 0.0% |
| MACD + 200D trend filter (4h) | -4.6% | +2.0% | -9.4% | -0.73 | -0.49 | 58 | 21% | 0.84 | 4.7% |
| HOLD (lump sum) | -6.6% | +0.0% | -34.4% | 0.09 | -0.19 | 0 | n/a | n/a | 0.1% |
| Bollinger squeeze breakout (4h) | -7.7% | -1.0% | -10.0% | -1.78 | -0.77 | 33 | 24% | 0.57 | 2.9% |
| Volatility-targeted hold | -8.4% | -1.7% | -29.7% | -0.15 | -0.28 | 4 | 0% | n/a | 0.2% |
| Donchian breakout (live #3) | -10.5% | -3.9% | -12.7% | -2.24 | -0.82 | 61 | 31% | 0.56 | 5.5% |
| Weekly DCA | -12.8% | -6.2% | -30.0% | -0.61 | -0.43 | 0 | n/a | n/a | 0.1% |
| EMA crossover (live #1) | -14.7% | -8.1% | -18.5% | -2.10 | -0.79 | 45 | 20% | 0.51 | 3.8% |

## Last 6 months (2026-05-01 to now)

| strategy | return | vs HOLD | max DD | Sortino | Calmar | closed trades | win rate | profit factor | fees (% of start) |
|---|---|---|---|---|---|---|---|---|---|
| Bollinger squeeze breakout (4h) | +8.9% | +7.0% | -3.0% | 4.73 | 6.10 | 11 | 36% | 3.49 | 0.8% |
| Weekly DCA | +7.8% | +6.0% | -10.7% | 1.26 | 1.51 | 0 | n/a | n/a | 0.1% |
| Trend filter (daily SMA, tuned 100-200d) | +4.3% | +2.4% | -14.1% | 0.67 | 0.61 | 1 | 0% | 0.00 | 0.2% |
| Volatility-targeted hold | +2.3% | +0.4% | -25.4% | 0.44 | 0.18 | 2 | 0% | n/a | 0.1% |
| HOLD (lump sum) | +1.8% | +0.0% | -29.3% | 0.42 | 0.13 | 0 | n/a | n/a | 0.1% |
| Donchian breakout (live #3) | +0.5% | -1.3% | -4.6% | 0.31 | 0.23 | 25 | 32% | 1.06 | 2.4% |
| RSI dip-buyer (live #2) | +0.0% | -1.8% | 0.0% | 0.00 | n/a | 0 | n/a | n/a | 0.0% |
| EMA crossover (live #1) | -2.3% | -4.2% | -9.4% | -0.55 | -0.48 | 30 | 13% | 0.87 | 2.9% |
| MACD + 200D trend filter (4h) | -7.0% | -8.8% | -8.1% | -2.90 | -1.64 | 21 | 24% | 0.35 | 2.0% |
| Time-series momentum (3 or 6 mo) | -17.6% | -19.4% | -23.3% | -1.99 | -1.37 | 2 | 50% | 0.12 | 0.5% |

## All out-of-sample (2022 to now) (2022-01-01 to now)

| strategy | return | vs HOLD | max DD | Sortino | Calmar | closed trades | win rate | profit factor | fees (% of start) |
|---|---|---|---|---|---|---|---|---|---|
| Trend filter (daily SMA, tuned 100-200d) | +167.3% | +99.0% | -34.3% | 1.16 | 0.66 | 31 | 26% | 1.09 | 11.7% |
| Time-series momentum (3 or 6 mo) | +94.7% | +26.4% | -38.0% | 0.85 | 0.39 | 32 | 34% | 1.12 | 8.0% |
| Weekly DCA | +82.9% | +14.6% | -50.7% | 0.81 | 0.26 | 0 | n/a | n/a | 0.1% |
| HOLD (lump sum) | +68.2% | +0.0% | -67.2% | 0.66 | 0.17 | 0 | n/a | n/a | 0.1% |
| Volatility-targeted hold | +44.8% | -23.5% | -59.8% | 0.56 | 0.13 | 18 | 0% | n/a | 1.1% |
| Bollinger squeeze breakout (4h) | +32.0% | -36.2% | -12.5% | 1.35 | 0.47 | 140 | 34% | 1.46 | 12.9% |
| MACD + 200D trend filter (4h) | +10.6% | -57.6% | -16.8% | 0.45 | 0.13 | 210 | 30% | 1.09 | 19.5% |
| RSI dip-buyer (live #2) | -7.0% | -75.2% | -8.6% | -1.08 | -0.17 | 26 | 31% | 0.44 | 2.4% |
| EMA crossover (live #1) | -15.8% | -84.1% | -29.4% | -0.35 | -0.12 | 201 | 20% | 0.87 | 17.0% |
| Donchian breakout (live #3) | -19.8% | -88.1% | -27.8% | -0.60 | -0.16 | 392 | 30% | 0.87 | 32.0% |

## Ranking (risk-adjusted, out-of-sample: Calmar, then Sortino) and verdicts

1. **Trend filter (daily SMA, tuned 100-200d)** (4h): PASS. OOS +167.3% (+99.0 pts vs HOLD), max DD -34.3%, Sortino 1.16, Calmar 0.66, 31 trades.
   Params chosen per test year (tuned on earlier data only): 2022: {'sma_days': 100}, 2023: {'sma_days': 100}, 2024: {'sma_days': 100}, 2025: {'sma_days': 100}, 2026: {'sma_days': 100}
2. **Bollinger squeeze breakout (4h)** (4h): PASS. OOS +32.0% (-36.2 pts vs HOLD), max DD -12.5%, Sortino 1.35, Calmar 0.47, 140 trades.
   Params chosen per test year (tuned on earlier data only): 2022: {'n': 20, 'squeeze_q': 0.25, 'atr_mult': 2.0}, 2023: {'n': 20, 'squeeze_q': 0.25, 'atr_mult': 2.0}, 2024: {'n': 20, 'squeeze_q': 0.25, 'atr_mult': 2.0}, 2025: {'n': 20, 'squeeze_q': 0.25, 'atr_mult': 2.0}, 2026: {'n': 20, 'squeeze_q': 0.25, 'atr_mult': 3.0}
3. **Time-series momentum (3 or 6 mo)** (4h): PASS. OOS +94.7% (+26.4 pts vs HOLD), max DD -38.0%, Sortino 0.85, Calmar 0.39, 32 trades.
   Params chosen per test year (tuned on earlier data only): 2022: {'lookback_days': 90}, 2023: {'lookback_days': 90}, 2024: {'lookback_days': 90}, 2025: {'lookback_days': 90}, 2026: {'lookback_days': 90}
4. **Volatility-targeted hold** (4h): FAIL. OOS +44.8% (-23.5 pts vs HOLD), max DD -59.8%, Sortino 0.56, Calmar 0.13, 18 trades. Why: only 18 closed trades out-of-sample (< 30): no edge claim possible; Sortino 0.56 <= HOLD 0.66; Calmar 0.13 <= HOLD 0.17.
   Params chosen per test year (tuned on earlier data only): 2022: {'target': 0.5, 'lookback_days': 60}, 2023: {'target': 0.5, 'lookback_days': 60}, 2024: {'target': 0.3, 'lookback_days': 60}, 2025: {'target': 0.3, 'lookback_days': 60}, 2026: {'target': 0.3, 'lookback_days': 60}
5. **MACD + 200D trend filter (4h)** (4h): FAIL. OOS +10.6% (-57.6 pts vs HOLD), max DD -16.8%, Sortino 0.45, Calmar 0.13, 210 trades. Why: Sortino 0.45 <= HOLD 0.66; Calmar 0.13 <= HOLD 0.17.
   Params chosen per test year (tuned on earlier data only): 2022: {'fast': 12, 'slow': 21, 'atr_mult': 2.0}, 2023: {'fast': 12, 'slow': 21, 'atr_mult': 2.0}, 2024: {'fast': 12, 'slow': 21, 'atr_mult': 2.0}, 2025: {'fast': 12, 'slow': 21, 'atr_mult': 2.0}, 2026: {'fast': 12, 'slow': 21, 'atr_mult': 2.0}
6. **EMA crossover (live #1)** (1h): FAIL. OOS -15.8% (-84.1 pts vs HOLD), max DD -29.4%, Sortino -0.35, Calmar -0.12, 201 trades. Why: Sortino -0.35 <= HOLD 0.66; Calmar -0.12 <= HOLD 0.17; lost money out-of-sample.
   Params chosen per test year (tuned on earlier data only): 2022: {'fast': 30, 'slow': 50, 'atr_mult': 2.0}, 2023: {'fast': 30, 'slow': 50, 'atr_mult': 2.0}, 2024: {'fast': 30, 'slow': 100, 'atr_mult': 3.0}, 2025: {'fast': 30, 'slow': 100, 'atr_mult': 3.0}, 2026: {'fast': 30, 'slow': 100, 'atr_mult': 3.0}
7. **Donchian breakout (live #3)** (1h): FAIL. OOS -19.8% (-88.1 pts vs HOLD), max DD -27.8%, Sortino -0.60, Calmar -0.16, 392 trades. Why: Sortino -0.60 <= HOLD 0.66; Calmar -0.16 <= HOLD 0.17; lost money out-of-sample.
   Params chosen per test year (tuned on earlier data only): 2022: {'entry_n': 20, 'exit_n': 20, 'atr_mult': 3.0}, 2023: {'entry_n': 20, 'exit_n': 20, 'atr_mult': 3.0}, 2024: {'entry_n': 100, 'exit_n': 10, 'atr_mult': 3.0}, 2025: {'entry_n': 100, 'exit_n': 10, 'atr_mult': 3.0}, 2026: {'entry_n': 100, 'exit_n': 10, 'atr_mult': 3.0}
8. **RSI dip-buyer (live #2)** (1h): FAIL. OOS -7.0% (-75.2 pts vs HOLD), max DD -8.6%, Sortino -1.08, Calmar -0.17, 26 trades. Why: only 26 closed trades out-of-sample (< 30): no edge claim possible; Sortino -1.08 <= HOLD 0.66; Calmar -0.17 <= HOLD 0.17; lost money out-of-sample.
   Params chosen per test year (tuned on earlier data only): 2022: {'low': 35, 'exit_rsi': 60, 'atr_mult': 1.5}, 2023: {'low': 25, 'exit_rsi': 50, 'atr_mult': 1.5}, 2024: {'low': 25, 'exit_rsi': 50, 'atr_mult': 1.5}, 2025: {'low': 25, 'exit_rsi': 50, 'atr_mult': 1.5}, 2026: {'low': 25, 'exit_rsi': 50, 'atr_mult': 1.5}

HOLD (2022 to now): +68.2%, max DD -67.2%, Sortino 0.66, Calmar 0.17.
Weekly DCA (2022 to now, money spread evenly over every week): +82.9%, max DD -50.7%, Sortino 0.81.

## Weak spots
- One asset, one exchange's prices, about 4.8 years out-of-sample. A few big BTC moves dominate every number.
- The candidates are well-known ideas chosen with hindsight (people already know trend filters worked on BTC). That selection is a bias no walk-forward can remove.
- Small grids were tuned per year; with 5 test years, luck still matters. Trend and momentum trade rarely: they only just clear the 30-trade bar, so their edge is thin evidence, not proof.
- Fees/slippage are modelled at 0.1% + 0.05% per side. Real slippage in fast markets can be worse; Indian taxes (30% + 1% TDS) are not included.
- Survivorship: BTC is the asset that survived; the same rules on coins that died would look very different.
- Risk sizing: MACD, Bollinger and the original 3 use the live risk rules (1% risk per trade, max 50% in a trade), so they are often only partly invested. Trend and momentum hold a full position when in.
