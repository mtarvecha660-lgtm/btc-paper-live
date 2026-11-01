"""Settings. Defaults live here; config.json in the kit root overrides them."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent          # the kit folder
DATA_DIR = ROOT / "data"                                 # cached candles
RUNS_DIR = ROOT / "runs"                                 # paper-trading state, journals, reports
RESULTS_DIR = ROOT / "results"                           # backtest outputs
STRATEGY_DIR = ROOT / "strategies"

DEFAULTS = {
    "symbol": "BTC/USDT",
    # Tried in order until one answers. binance_vision is Binance's public
    # market-data mirror (same candles as Binance, works where api.binance.com is blocked).
    "sources": ["binance", "binance_vision", "okx", "bitstamp", "coinbase", "kraken"],
    "starting_balance_usdt": 10000.0,
    "fee_pct": 0.1,                 # per side, % of trade value (Binance spot default is 0.1%)
    "slippage_pct": 0.05,           # per side, price moves against you by this much
    "risk_per_trade_pct": 1.0,      # % of equity you lose if the stop is hit
    "max_position_pct": 50.0,       # never put more than this % of equity in one trade
    "daily_loss_limit_pct": 3.0,    # equity down this much since the day started -> flat + halt till tomorrow
    "min_trade_usdt": 10.0,
    "allow_short": False,           # long-only spot. Shorting is not implemented (on purpose).
    "leverage": 1,                  # fixed at 1. The engine refuses anything else.
    "timezone": "Asia/Kolkata",     # where a "day" starts for the daily loss limit and reports
    "train_pct": 70.0,              # backtest: first 70% = train, last 30% = test
    "warmup_bars": 300,             # extra history fetched so indicators are ready at the start
    "poll_seconds": 30,             # paper loop: how often to check for a new closed candle
    "usd_inr_fallback": 88.0,       # only used if every live USDT->INR source fails
}


def load_config(overrides=None):
    cfg = dict(DEFAULTS)
    f = ROOT / "config.json"
    if f.exists():
        user = json.loads(f.read_text(encoding="utf-8"))
        cfg.update({k: v for k, v in user.items() if not k.startswith("_")})
    if overrides:
        cfg.update({k: v for k, v in overrides.items() if v is not None})
    if cfg.get("leverage", 1) != 1:
        raise SystemExit("leverage must be 1: this kit never uses leverage.")
    if cfg.get("allow_short"):
        raise SystemExit("allow_short=true is not supported: this kit is long-only spot paper trading.")
    return cfg


TF_MINUTES = {"1m": 1, "5m": 5, "15m": 15, "30m": 30, "1h": 60, "2h": 120, "4h": 240, "1d": 1440}


def tf_minutes(tf):
    if tf not in TF_MINUTES:
        raise SystemExit(f"unsupported timeframe {tf!r}; use one of {', '.join(TF_MINUTES)}")
    return TF_MINUTES[tf]
