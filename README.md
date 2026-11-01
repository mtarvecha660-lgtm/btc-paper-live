# BTC Paper Bot · live

**PAPER TRADING. Virtual money only.** No exchange account, no API keys, no real orders. Nothing in this repo can touch real money.

**Dashboard (open on your phone): https://mtarvecha660-lgtm.github.io/btc-paper-live/**

Three trading strategies race against simply holding Bitcoin. Each account starts with a virtual **₹5,00,000**. The bot runs on GitHub's servers every ~15 minutes, for free, whether your laptop is on or off.

| Account | What it does |
|---|---|
| EMA Crossover | Trend following: buys when the 20-hour average crosses above the 100-hour one (only above the 200-hour trend), sells when it crosses back. |
| RSI Dip-Buyer | Mean reversion: buys sharp dips (RSI under 35), sells on the bounce (RSI 50). |
| Donchian Breakout | Buys when price breaks the 100-hour high, sells on a 10-hour low. |
| Just Hold BTC | Benchmark: buys once with everything at the start and never sells. |

The strategy settings are the 1-hour versions that did least badly in the 180-day backtests (`results.md`). Honest note: **in those backtests none of them beat just holding BTC.** That is what this live paper run is for: see how they behave on prices nobody has seen yet.

## How it works

1. Every ~15 min, GitHub Actions runs `live/tick.py` (`.github/workflows/paper-tick.yml`).
2. It reads public BTC/USDT candles (Binance's public data mirror first; OKX, Bitstamp, Coinbase and Kraken are fallbacks). GitHub's servers are in the US, where Binance's main API is blocked, which is why the mirror goes first.
3. On each **closed 1-hour candle**, each strategy decides BUY, SELL or WAIT. A buy or sell fills at the next candle's open with a **0.1% fee + 0.05% slippage**, using the same engine as the backtests (`btcpaper/engine.py`).
4. Risk rules: 1% of the account risked per trade (the stop-loss sets the size), max 50% of the account in one trade, a stop on every trade, and trading pauses for the rest of the day (IST) after a 3% loss. No leverage, no shorting.
5. The bot commits the results back here (`live/`) and rebuilds the dashboard.

If every price source fails, that run is logged as `skipped` in `live/ticks.csv` and the next run catches up on any candles it missed (up to 7 days).

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
- GitHub can start scheduled runs late (sometimes 5 to 30+ minutes under load). Fills still use the right candle's open, so late runs don't change the results much.
- The repo is public, so anyone with the link can see the paper results. There are no secrets in it.

## Safety

Paper results are not real results. Real trading adds things paper can't show (your own emotions, exchange outages, liquidity). Most strategies lose to fees. Run paper for weeks before even thinking about real money. In India, crypto gains are taxed at a flat 30% (plus cess), with 1% TDS on transfers (see `KIT_README.md`). This is not financial advice.
