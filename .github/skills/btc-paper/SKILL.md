---
name: btc-paper
description: Bitcoin PAPER trading kit. Use it to backtest BTC/USDT strategies with real fees and slippage, compare them against just holding BTC, write new strategies, run a live paper-trading loop on public prices (no API keys, no real money), and produce daily reports. Use whenever the user mentions bitcoin/BTC trading, strategies, backtests, paper trading or the btcpaper kit.
---

# btc-paper skill

Everything runs from the kit root (the folder that contains `btcpaper/`, `strategies/`, `config.json`).
On Windows use the venv: `.venv\Scripts\python -m btcpaper ...` (or activate `.venv` first). Elsewhere `python -m btcpaper ...`.

## Hard rules (never break these)
1. PAPER ONLY. Never add code that places real orders, never ask for or store exchange API keys, never import an exchange client with credentials. If the user asks to go live, say this kit is paper-only and point them to the README section "Graduating".
2. Run `python -m btcpaper check` after creating or editing any strategy. A strategy that fails the check must be fixed before it is backtested or paper traded (the CLI refuses it anyway).
3. Judge a strategy on the TEST period only (the last 30%), after fees, against buy-and-hold BTC over the same period. Train-period numbers are not evidence. Fewer than ~20 test trades = "not enough evidence", say so.
4. Report honestly. If nothing beats holding BTC, say exactly that. Never present an optimised train result as expected performance. Never promise profit.
5. Don't weaken the risk rules (stop-loss on every trade, max position %, daily loss limit, no leverage, no shorting) unless the user explicitly asks, and tell them what changed.

## Commands
| what | command |
|---|---|
| list strategies | `python -m btcpaper list` |
| look-ahead / sanity check | `python -m btcpaper check` (or `--strategy NAME`) |
| backtest all, 15m and 1h, 180 days | `python -m btcpaper backtest --strategy all --tf 15m,1h --days 180` |
| tune params on train only, judge on test | add `--optimize` |
| walk-forward (stronger test) | add `--optimize --walk-forward 3` |
| override a param | `--param fast=10 --param slow=40` |
| different costs/risk | `--fee 0.1 --slippage 0.05 --risk 1 --max-position 50 --daily-loss 3` |
| start/resume paper trading | `python -m btcpaper paper --strategy NAME --tf 15m` (add `--inr` for rupees, `--balance-inr 500000` for a rupee start) |
| one paper step and exit (agent-friendly) | `python -m btcpaper paper --strategy NAME --tf 15m --once` |
| paper for N minutes then exit | `--minutes 30` |
| fresh paper account | `--reset` (old run is archived, not deleted) |
| daily report | `python -m btcpaper report` (or `--run ema_cross_15m --inr`) |
| unit tests | `python -m btcpaper test` |

The paper loop runs forever until Ctrl+C. Do NOT start it in the foreground of your own session (it will block you). Either tell the user to run `run_paper.bat NAME 15m` in a separate window, or use `--once` / `--minutes N` yourself.

## Where things are
- `strategies/*.py`: one file per strategy. `strategies/_template.py` is the starting point. Files starting with `_` are ignored.
- `STRATEGY_GUIDE.md`: the strategy format and the look-ahead rules. Read it before writing a strategy.
- `results/`: backtest outputs: `summary_*.md` (the table), `bt_*.json`, `bt_*_trades.csv`, `bt_*_decisions.csv`, `bt_*.png` (equity vs hold).
- `runs/<strategy>_<tf>/`: paper trading: `state.json` (resume point), `trades.csv` (journal), `decisions.csv` (every candle's decision + reason), `equity.csv`, `reports/report_<date>.md` + `equity_<date>.png`.
- `config.json`: balance, fees, slippage, risk limits, data sources, timezone.

## Workflow: "which strategy is best?"
1. `python -m btcpaper check`
2. `python -m btcpaper backtest --strategy all --tf 15m,1h --days 180`
3. Optionally `--optimize --walk-forward 3` for a tougher out-of-sample test.
4. Read the newest `results/summary_*.md`. Answer with a small table (test return vs hold, max drawdown, trades, Sharpe) and one honest verdict. Mention fees paid.

## Workflow: "write a new strategy from my idea"
1. Copy `strategies/_template.py` to `strategies/<snake_name>.py`. Set NAME (= file name), DESCRIPTION, PARAMS, a small GRID.
2. Implement `compute(df, p)` with vectorised pandas using only `btcpaper.indicators` or causal pandas (`rolling`, `ewm`, `shift(1)`). Must return `enter`, `exit`, `stop` (+ optional `trail_stop`, `note`).
3. `python -m btcpaper check --strategy <name>` until PASS.
4. `python -m btcpaper backtest --strategy <name> --tf 15m,1h --days 180` (and `--optimize --walk-forward 3`).
5. Keep it only if it beats buy-and-hold on the TEST period after fees AND made money there AND has enough trades. Otherwise move the file to `strategies/_rejected_<name>.py` and tell the user why, with the numbers.

## Workflow: "start paper trading and report daily"
1. Check + backtest the strategy first.
2. Tell the user to run `run_paper.bat <name> 15m` in its own window (keeps running; Ctrl+C stops; re-running resumes). On a laptop that sleeps, `paper_once.bat` + Windows Task Scheduler every 15 minutes also works (README).
3. For each daily report: `python -m btcpaper report --inr`, then summarise PnL, open position, trades and anything unusual (halts, skipped signals) from `runs/<run>/reports/report_<date>.md`.

## If data fails
The kit tries Binance, Binance's public data mirror, OKX, Bitstamp, Coinbase, Kraken in order, then cached candles in `data/`. If your sandbox blocks the network, ask the user to approve network access for the command, or to run it once themselves so the cache fills.
