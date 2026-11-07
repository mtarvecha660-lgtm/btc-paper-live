<div align="center">

# BTC Paper Bot

**A 24/7 Bitcoin paper-trading lab: four strategies race against simply holding BTC, with virtual money only.**

![Python](https://img.shields.io/badge/python-3.11-3776AB?logo=python&logoColor=white)
![GitHub Actions](https://img.shields.io/badge/runs%20on-GitHub%20Actions-2088FF?logo=githubactions&logoColor=white)
![Mode](https://img.shields.io/badge/mode-PAPER%20ONLY-critical)
![Money](https://img.shields.io/badge/money-virtual%20%E2%82%B95%2C00%2C000-lightgrey)

[Live dashboard](https://mtarvecha660-lgtm.github.io/btc-paper-live/) · [V2 regime test](https://mtarvecha660-lgtm.github.io/btc-paper-live/v2.html) · [Not financial advice](#safety)

</div>

> **PAPER ONLY.** Virtual money, no exchange account, no API keys, no real orders. Most retail trading strategies lose money, and this is not financial advice.

Three trading strategies race against simply holding Bitcoin. Each account starts with a virtual **₹5,00,000**. The bot runs on GitHub's servers every ~15 minutes, for free, whether your laptop is on or off.

| Account | What it does |
|---|---|
| EMA Crossover | Trend following: buys when the 20-hour average crosses above the 100-hour one (only above the 200-hour trend), sells when it crosses back. |
| RSI Dip-Buyer | Mean reversion: buys sharp dips (RSI under 35), sells on the bounce (RSI 50). |
| Donchian Breakout | Buys when price breaks the 100-hour high, sells on a 10-hour low. |
| Just Hold BTC | Benchmark: buys once with everything at the start and never sells. |

**V2 accounts (added after a multi-year regime test, see below):**

| Account | What it does |
|---|---|
| Trend Filter (100-day SMA) | Holds BTC fully while the last daily close is above its 100-day average, else cash (4h candles). |
| Bollinger Squeeze (4h) | Waits for a quiet market (narrow bands), buys a 4h close above the upper band; exits below the middle band; ATR stop; 1% risk per trade. |
| 3-Month Momentum | Holds BTC fully while its 90-day return is positive, else cash (4h candles). |
| Weekly DCA (52 weeks) | Second benchmark: buys ₹5 lakh ÷ 52 every week, never sells. |

The original 3 strategies' settings are the 1-hour versions that did least badly in the 180-day backtests (`results.md`). Honest note: **in those backtests none of them beat just holding BTC.** That is what this live paper run is for: see how they behave on prices nobody has seen yet.

## V2: the regime test

`research/v2_regimes.py` pulls BTC/USDT hourly candles from June 2020, and tests 8 strategies with an anchored walk-forward: each test year (2022, 2023, 2024, 2025, 2026 so far) uses settings tuned only on earlier years. Results are reported for the 2022 bear market, the 2023-24 bull market, the 2025 range and the last 6 months, against lump-sum HOLD and weekly DCA, with the same costs. A strategy PASSES only with at least 30 out-of-sample trades, better Sortino and Calmar than HOLD, and a profit.

- Page: https://mtarvecha660-lgtm.github.io/btc-paper-live/v2.html
- Full tables: `RESULTS_V2.md`
- Re-run: `python research/v2_regimes.py` (downloads the history once into `data/`, which is not committed)

Passed: the 100-day trend filter, the Bollinger squeeze (4h) and 3-month momentum, so they became live paper accounts. Failed: MACD + trend, volatility-targeted hold, and the original 3. These are backtests: a pass is a reason to paper-trade a strategy, not proof it will work.

## How it works

1. Every ~15 min, GitHub Actions runs `live/tick.py` (`.github/workflows/paper-tick.yml`).
2. It reads public BTC/USDT candles (Binance's public data mirror first; OKX, Bitstamp, Coinbase and Kraken are fallbacks). GitHub's servers are in the US, where Binance's main API is blocked, which is why the mirror goes first.
3. On each **closed candle** (1 hour for the original 3, 4 hours for the V2 ones), each strategy decides BUY, SELL or WAIT. A buy or sell fills at the next candle's open with a **0.1% fee + 0.05% slippage**, using the same engine as the backtests (`btcpaper/engine.py`).
4. Risk rules: 1% of the account risked per trade (the stop-loss sets the size), max 50% of the account in one trade, a stop on every trade, and trading pauses for the rest of the day (IST) after a 3% loss. No leverage, no shorting. The two "allocation" V2 accounts (trend filter, momentum) are the exception, set in `live/accounts.json` under `risk`: they hold a full position when in, keep a 30% crash stop, and have no daily pause, because that is the strategy that was tested.
5. The bot commits the results back here (`live/`) and rebuilds the dashboard.

If every price source fails, that run is logged as `skipped` in `live/ticks.csv`, the GitHub run turns **red** (so you notice), whatever did succeed is still committed, and the next run catches up on any candles it missed (up to 7 days). If the last good run is more than 45 minutes old, the dashboard shows a red "out of date" banner. GitHub may email you about red runs; one or two in a row is usually a price-source hiccup.

**Fair comparison:** every value on the dashboard and in the backtests counts an open position as if it were sold right now, with the fee and slippage. That's the same rule as "Just Hold BTC", which pays to buy and would pay to sell. So Hold starts slightly below ₹5,00,000 (the round-trip cost), and a strategy holding BTC is never flattered by a sale it hasn't paid for.

**Metrics** (dashboard cards and `python -m btcpaper backtest`): return vs Hold, profit factor (money won ÷ money lost on closed trades), expectancy per trade, average win and average loss, fees as a % of the before-fee P&L, Sortino, and monthly returns.

₹ values use the USDT→INR rate from when the bot started (in `live/meta.json`), so ₹ and % always tell the same story.

### Files

| Path | What's in it |
|---|---|
| `live/accounts.json` | the accounts and their strategy settings |
| `live/state/<account>/trades.csv` | every paper trade, with fee, P&L and the reason |
| `live/state/<account>/decisions.csv` | one row per hourly candle: what the bot decided and why |
| `live/state/<account>/equity.csv` | account value after each candle |
| `live/state/<account>/state.json` | cash, open position, stop (the bot resumes from this) |
| `live/ticks.csv` | a log of the bot's runs (ok / skipped / error), last ~6 days |
| `live/latest.json` | the numbers the dashboard shows |
| `docs/` | the dashboard (plain HTML + Chart.js) |
| `btcpaper/`, `strategies/` | the paper-trading kit (backtest, paper, report, check) |

## Change strategies with Codex

Clone the repo, open the folder in Codex, and ask in plain words. It reads `AGENTS.md` and the btc-paper skill. Examples:

- "Use the btc-paper skill. Write a new strategy based on <your idea>, backtest it on 1h for 180 days, and if it beats the others on the test period, add it to the live bot as a new account in live/accounts.json. Then push."
- "Change the RSI Dip-Buyer in live/accounts.json to buy below RSI 30 instead of 35. Backtest it first. Push."
- "Reset all live paper accounts and start fresh." (Codex deletes `live/state/` and `live/meta.json`; the next run starts new ₹5 lakh accounts.)
- "Look at live/state/*/trades.csv and tell me which strategy is doing best and why."

Always pull before you push, because the bot commits every ~15 minutes. A new account id starts with a fresh ₹5,00,000. Changing settings of an existing account keeps its balance and history.

Run it on your own laptop instead: `setup_windows.bat` then `python live/tick.py` (see `KIT_README.md` for the full kit: backtests, reports, the paper loop).

## Stop it / start it

- **Pause:** GitHub → this repo → **Actions** → **paper-tick** → `...` menu → **Disable workflow**. Turn it back on the same way (**Enable workflow**).
- **Run once now:** Actions → paper-tick → **Run workflow**.
- **Remove for good:** delete `.github/workflows/paper-tick.yml`, or delete the repo.

**60-day rule:** GitHub automatically disables scheduled workflows in a public repo when there has been no repository activity for 60 days. The bot commits on every run, but GitHub doesn't say clearly whether a bot's own commits count as activity. If it ever stops, GitHub emails you, and you re-enable it in the Actions tab (or push any small commit).

## Costs and limits

- Free: GitHub Actions is free for public repos, and Pages is free.
- GitHub can start scheduled runs late (sometimes 5 to 30+ minutes under load), and for a brand-new repo its schedule can take hours to start. So the workflow has a **backup ticker**: if no scheduled run has happened in the last 40 minutes, each run waits until ~14 minutes after it began and starts the next one itself. Once GitHub's schedule is running, the backup does nothing. Fills still use the right candle's open, so late runs don't change results much.
- The repo is public, so anyone with the link can see the paper results. There are no secrets in it.

## Safety

Paper results are not real results. Real trading adds things paper can't show (your own emotions, exchange outages, liquidity). Most strategies lose to fees. Run paper for weeks before even thinking about real money. In India, crypto gains are taxed at a flat 30% (plus cess), with 1% TDS on transfers (see `KIT_README.md`). This is not financial advice.
