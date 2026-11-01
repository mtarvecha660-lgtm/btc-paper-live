# btc-paper-kit: Bitcoin paper trading you can drive with Codex

Backtest Bitcoin strategies with real fees, compare them against just holding BTC, then paper-trade the
best one on live prices with a virtual balance. Codex (or Copilot / Claude) can run all of it and write new
strategies for you through the included skill.

**Paper only.** No real money, no exchange account, no API keys. There is no code here that can place a real order.
It only reads public price data.

## What's inside
- `python -m btcpaper backtest`: 180 days of real BTC/USDT candles, 0.1% fee + 0.05% slippage per side, fills at the
  next candle's open (no look-ahead), train/test split (70/30), optional parameter tuning on train only and walk-forward.
  Reports return, max drawdown, win rate, trades, Sharpe, time in market, fees paid, and the same numbers for just holding BTC.
- `python -m btcpaper paper`: a live paper-trading loop. Polls new candles, fills simulated orders at the next open with fees
  and slippage, starts with 10,000 USDT (or a rupee amount), saves its state after every candle so a restart resumes,
  writes a trade journal and a reason for every decision. Ctrl+C stops it safely.
- `python -m btcpaper report`: daily report with an equity chart (PNG), today's and total PnL, the open position, and every decision with its reason.
- `python -m btcpaper check`: rejects strategies that peek into the future.
- 3 starter strategies (EMA crossover, RSI mean-reversion, Donchian breakout), each with an ATR stop-loss.
- Risk rules on every trade: stop-loss always set, max 50% of equity per trade, 1% of equity risked per trade, 3% daily loss limit that halts trading until tomorrow, no leverage, no shorting.
- Prices in USDT, with rupee (INR) equivalents on request (`--inr`).
- Data: Binance public candles, with automatic fallback to Binance's public data mirror, OKX, Bitstamp, Coinbase and Kraken
  if one is blocked, then to cached candles if you're offline.

## Setup on Windows 11 (5 minutes)
1. Install Python 3.11 or newer from https://www.python.org/downloads/ . In the installer, tick **"Add python.exe to PATH"**.
2. Unzip this folder somewhere simple like `C:\btc-paper-kit` (not inside OneDrive: OneDrive can lock files the bot is writing).
3. Double-click `setup_windows.bat`. It creates `.venv`, installs ccxt, pandas, numpy and matplotlib, runs the tests and the strategy check.
4. Open the folder in Codex (or VS Code with Copilot). The skill is picked up from `.agents/skills/btc-paper/` (Codex),
   `.github/skills/btc-paper/` (Copilot) and `.claude/skills/btc-paper/` (Claude Code). `AGENTS.md` points agents to it.

Run commands yourself from a terminal opened in the folder:
```
.venv\Scripts\python -m btcpaper backtest --strategy all --tf 15m,1h --days 180
.venv\Scripts\python -m btcpaper paper --strategy ema_cross --tf 15m --inr
.venv\Scripts\python -m btcpaper report --inr
```
Shortcuts: `run_paper.bat ema_cross 15m` (paper loop in its own window), `report.bat` (today's report).

## Prompts for Codex
Paste these as they are:

1. `Use the btc-paper skill. Backtest all strategies on 15m and 1h for the last 180 days and tell me which is best after fees vs just holding BTC. Judge on the test period only.`
2. `Use the btc-paper skill. Write a new strategy based on <your idea, e.g. "buy when price bounces off the 200 EMA with RSI under 40">, run the look-ahead check, backtest it with --optimize --walk-forward 3, and only keep it if it beats holding BTC on the test period after fees. Show me the numbers either way.`
3. `Use the btc-paper skill. Start paper trading with <strategy> on 15m with a 5 lakh rupee virtual balance. Tell me the exact command to run in a separate window, then give me a report every day: PnL in rupees, open position, trades and why each was made.`
4. `Use the btc-paper skill. Read today's paper trading report and explain in simple words what the bot did and whether it's doing better or worse than just holding BTC.`

Tip: the paper loop runs until you stop it, so let it run in its own window (`run_paper.bat`), not inside Codex.
If Codex says the network is blocked, approve the command when it asks, or allow network access for the workspace.

## How to read the results
- **Only the test period counts.** It's the last 30% of the data; nothing was tuned on it. Train numbers are not evidence.
- **"hold BTC"** is what you'd have made buying BTC at the start and doing nothing, with the same fees.
- **Losing less than holding in a falling market** means the strategy sat in cash. That's not an edge.
- **Fewer than ~20 trades** in the test period means the result could easily be luck.
- `--walk-forward 3` is the tougher test: tune on one window, trade the next, three times in a row.

## Paper trading on a laptop
- The loop only runs while your laptop is awake. If it sleeps, the next start catches up on the candles it missed
  (up to 7 days), applying the same rules as if it had been running, and says so.
- Want it without a window open? Use Windows Task Scheduler with `paper_once.bat`, which processes new candles and exits:
  `schtasks /Create /SC MINUTE /MO 15 /TN btcpaper /TR "C:\btc-paper-kit\paper_once.bat ema_cross 15m"` (adjust the path).
  Output goes to `runs\task_log.txt`.
- Don't keep `trades.csv` open in Excel while the bot runs: Excel locks it. The bot writes to a side file and warns you if that happens.
- Files: `runs\<strategy>_<tf>\state.json` (balance and position), `trades.csv`, `decisions.csv`, `equity.csv`, `reports\`.
  `--reset` starts a fresh account (the old one is archived, not deleted).

## Settings
Edit `config.json`: starting balance, fee, slippage, risk per trade, max position, daily loss limit, data sources, timezone.
Every command also takes `--fee`, `--slippage`, `--risk`, `--max-position`, `--daily-loss` and `--param name=value`.
Leverage and shorting are switched off and not implemented. That's on purpose.

## Safety, briefly
- This is paper trading. Results use real prices but simulated fills; real fills can be worse.
- A good backtest doesn't predict the future. Most simple strategies lose to fees and to just holding BTC, including the three
  starter strategies here (see `results.md`).
- Don't put real money in until a strategy has made money in paper trading for several weeks, ideally across both up and down
  markets, and you understand why it works.
- If you ever trade for real in India: profit on crypto is taxed at a flat 30% (plus 4% cess), losses can't be set off against
  other income, and 1% TDS is deducted on crypto sales above the yearly threshold (Income Tax Act sections 115BBH and 194S; Budget
  2026-27 kept both unchanged). Sources: https://www.incometaxindia.gov.in/w/section-115bbh-1 ,
  https://tokentax.co/blog/guide-to-crypto-taxes-in-india . Check with a CA before filing; this isn't tax advice.
- Use only exchanges registered with India's FIU, and never share API keys with any tool or person.

## Graduating to a bigger tool
When a strategy has survived weeks of paper trading here, **Freqtrade** (free, open source, https://www.freqtrade.io) is the
natural next step. It has a dry-run (paper) mode on live exchange data, a much bigger backtesting and hyper-optimisation toolkit,
its own look-ahead and recursive-analysis checks, a web UI and Telegram control. Strategies from this kit port over easily
(`enter` -> `populate_entry_trend`, `exit` -> `populate_exit_trend`, `stop` -> `custom_stoploss`).
On Windows, Freqtrade recommends Docker Desktop or WSL2; a native install needs TA-Lib and Python 3.12+.

Other options: **Jesse** (https://jesse.trade, clean Python strategies, paper trading, and a built-in MCP server that Codex can
connect to; needs Postgres and Redis, easiest through Docker) and **Hummingbot** (market-making bots with paper-trade connectors).

## Folder map
```
btcpaper/           the engine (data, indicators, simulator, backtest, paper loop, report, checks)
strategies/         one file per strategy; _template.py to copy
tests/              unit tests: fee math, no look-ahead, risk limits, live loop = backtest
results/            backtest outputs (tables, trades, decisions, charts)
runs/               paper trading accounts
data/               cached candles
STRATEGY_GUIDE.md   how to write a strategy (and how not to fool yourself)
.agents/skills/btc-paper/SKILL.md   the Codex skill (copies in .github/skills and .claude/skills)
```
