# Forward-test evaluation criteria (locked before results)

Written and committed on **2026-11-01 (17:10 IST)**, before looking at any forward results.
The forward test began at **2026-11-01 09:08 UTC**. This file is the scorecard. Any later change must go in a new dated section with its reason, and the original stays as written.

## Ground rules
1. **No tuning during the test.** The settings on 1 Nov 2026 are frozen. Changing a setting or strategy creates a NEW account with its own start date. The old account keeps running.
2. **Forward results only.** Backtest numbers (RESULTS_V2.md) are never mixed into this scorecard.
3. **Same valuation for everyone.** Every account is valued as if it sold now, with fee (0.1%) and slippage (0.05%), including HOLD and DCA.
4. **Paper only.** Passing this scorecard does NOT mean using real money. At most it earns a longer paper test.

## Candidates and benchmarks
- Candidates: Trend Filter (100-day SMA), 3-Month Momentum, Bollinger Squeeze (4h).
- Also tracked, but no verdict expected: EMA Crossover, RSI Dip-Buyer, Donchian Breakout.
- Benchmarks: Just Hold BTC, and Weekly DCA (52 weeks).

## Review dates
- **Day 30 (1 Dec 2026)** and **Day 90 (30 Jan 2027):** health check only. No pass/fail.
- **Day 180 (30 Apr 2027):** verdict for Bollinger Squeeze.
- **Day 365 (1 Nov 2027):** verdict for Trend Filter and 3-Month Momentum. They are slow and trade only about 6–7 times a year, so 180 days is too few trades to judge them.

## A candidate PASSES only if ALL of these hold at its verdict date
| # | Test | Rule |
|---|------|------|
| 1 | Net return | Return after all costs is above 0%. |
| 2 | Risk-adjusted vs benchmarks | Sortino AND Calmar beat both HOLD and DCA over the same dates. |
| 3 | Drawdown | Max drawdown no worse than 60% of HOLD's max drawdown over the same dates, and never worse than -35%. |
| 4 | Trade count | At least 6 closed trades (Trend/Momentum, 365d) or 12 (Bollinger, 180d). Fewer means **"not enough evidence"**, not a pass. |
| 5 | Consistency | Not worse than HOLD on a risk-adjusted basis in more than half of the 2-month blocks. |
| 6 | Matches its backtest | Its forward behaviour is plausible against its backtest: trades per month within 0.5x–2x, and average loss per trade no bigger than 2x the backtest's. |

Raw return vs HOLD is **reported, not required**. A strategy can pass by taking much less risk for a smaller return. The dashboard always shows it next to HOLD so nobody is fooled.

## Early stop (any time)
An account is marked **FAILED early** if:
- its drawdown goes past 1.5x its backtest max drawdown (Trend -51%, Momentum -57%, Bollinger -19%), or
- it shows a bug (a trade the rules should not allow, or a wrong valuation). The bug is fixed in a new account, and the clock restarts.

## What each outcome means
- **PASS:** keep paper-trading for another 12 months with the same rules. Still no real money.
- **NOT ENOUGH EVIDENCE:** extend the test. Do not change the strategy.
- **FAIL:** stop tracking it as a candidate, and record why.

## Clarification — 2026-11-01 17:15 IST (still before any forward results; thresholds unchanged)
Raised in review: test #5 needed an exact calculation. This defines it and changes no threshold.

**Test #5 (consistency), exact method**
- Split the forward window into consecutive 2-month blocks starting at the account's start date. A block shorter than 30 days at the end is dropped.
- In each block, compute the **Sortino ratio of daily returns** for the candidate and for HOLD, using the same valuation and the same days. Sortino only, not Calmar: Calmar over 2 months is too noisy to be meaningful.
- If a Sortino is undefined in a block (no down days, e.g. sitting in cash), compare **net return** in that block instead.
- The block is **"worse"** if the candidate's value is strictly lower than HOLD's.
- Test #5 passes if worse blocks are **no more than half** of all blocks (for example, 3 of 6 is OK and 4 of 6 fails).

**Note on test #4 (trade count)**
The trade minimum only stops a premature pass. It is not proof. A PASS on 6–12 trades is a weak pass, and the verdict must say so with the actual trade count next to it.
