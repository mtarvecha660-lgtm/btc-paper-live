import os

os.environ["MPLBACKEND"] = "Agg"       # no window needed; also avoids broken backend settings
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def equity_png(times, equity, closes, path, title, split_time=None, start_balance=None):
    equity = np.asarray(equity, dtype=float)
    closes = np.asarray(closes, dtype=float)
    base = start_balance or equity[0]
    hold = base * closes / closes[0]
    fig, ax = plt.subplots(figsize=(10, 4.5), dpi=110)
    ax.plot(times, equity, label="strategy (paper)", lw=1.6, color="#1f77b4")
    ax.plot(times, hold, label="just holding BTC", lw=1.0, color="#999999")
    if split_time is not None:
        ax.axvline(split_time, color="#d62728", ls="--", lw=1)
        ax.text(split_time, ax.get_ylim()[1], " test period ->", color="#d62728", va="top", fontsize=8)
    ax.set_title(title)
    ax.set_ylabel("equity (USDT)")
    ax.set_xlabel("time (UTC)")
    ax.grid(alpha=0.3)
    ax.legend(loc="best")
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
