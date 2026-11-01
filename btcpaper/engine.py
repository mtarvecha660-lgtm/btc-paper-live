"""The simulator. Backtests and the live paper loop both run THIS code, candle by candle,
so a paper result and a backtest result mean the same thing.

Timing rule (no look-ahead):
  * a signal is read on candle i AFTER it has closed,
  * the order fills at the OPEN of candle i+1, with slippage and fees,
  * the stop-loss is checked against each candle's low; a gap below the stop fills at the open.
There is no function here (or anywhere in this kit) that talks to a real exchange account.
"""
import math
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


def new_state(balance):
    return {
        "cash": float(balance), "qty": 0.0, "start_balance": float(balance),
        "entry_price": None, "entry_ts": None, "entry_fee": 0.0, "entry_cost": 0.0, "entry_reason": "",
        "stop": None, "pending": None,
        "day": None, "day_start_equity": float(balance), "halted_day": None,
        "last_ts": None, "trade_id": 0, "fees_paid": 0.0, "realized_pnl": 0.0,
        "last_close": None, "opened_ts": None, "open_notes": [],
    }


class Engine:
    def __init__(self, cfg, state=None):
        self.cfg = cfg
        self.fee = cfg["fee_pct"] / 100.0
        self.slip = cfg["slippage_pct"] / 100.0
        self.risk = cfg["risk_per_trade_pct"] / 100.0
        self.maxpos = cfg["max_position_pct"] / 100.0
        self.daily_limit = cfg["daily_loss_limit_pct"] / 100.0
        self.min_trade = cfg["min_trade_usdt"]
        self.tz = ZoneInfo(cfg.get("timezone", "UTC"))
        self.s = state or new_state(cfg["starting_balance_usdt"])
        if cfg.get("leverage", 1) != 1 or cfg.get("allow_short"):
            raise ValueError("leverage and shorting are not supported")

    # ---------- helpers ----------
    def equity(self, price):
        return self.s["cash"] + self.s["qty"] * price

    def in_position(self):
        return self.s["qty"] > 0

    def _day(self, ts_ms):
        return datetime.fromtimestamp(ts_ms / 1000, tz=self.tz).strftime("%Y-%m-%d")

    def size_order(self, equity, cash, price, stop):
        """USDT to spend on a buy at `price` with stop `stop`. Returns (notional, why)."""
        if stop is None or not math.isfinite(stop) or stop <= 0 or stop >= price:
            return 0.0, "no valid stop-loss below the entry price"
        dist = (price - stop) / price
        by_risk = equity * self.risk / dist          # lose risk% of equity if the stop is hit
        by_cap = equity * self.maxpos                # never more than max_position% of equity
        by_cash = cash / (1 + self.fee)              # no leverage: can't spend money you don't have
        notional = min(by_risk, by_cap, by_cash)
        if notional < self.min_trade:
            return 0.0, f"order too small ({notional:.2f} USDT)"
        limiter = "risk" if notional == by_risk else ("max_position" if notional == by_cap else "cash")
        return notional, f"size {notional:.2f} USDT (limited by {limiter})"

    def _buy(self, ts, price_ref, stop, reason):
        s = self.s
        price = price_ref * (1 + self.slip)
        if stop is not None and price <= stop:
            return None, f"cancelled buy: opened at {price_ref:.2f}, already below stop {stop:.2f}"
        notional, why = self.size_order(s["cash"], s["cash"], price, stop)
        if notional <= 0:
            return None, f"skipped buy: {why}"
        qty = notional / price
        fee = notional * self.fee
        s["cash"] -= notional + fee
        s["qty"] = qty
        s["entry_price"], s["entry_ts"], s["entry_fee"], s["entry_cost"] = price, ts, fee, notional
        s["entry_reason"], s["stop"] = reason, stop
        s["fees_paid"] += fee
        s["trade_id"] += 1
        ev = {"trade_id": s["trade_id"], "ts": ts, "side": "BUY", "price": price, "qty": qty,
              "value": notional, "fee": fee, "pnl": None, "reason": reason, "stop": stop}
        return ev, f"BUY {qty:.6f} BTC @ {price:.2f} ({why}), stop {stop:.2f}"

    def _sell(self, ts, price_ref, reason, apply_slip=True):
        s = self.s
        price = price_ref * (1 - self.slip) if apply_slip else price_ref
        qty = s["qty"]
        proceeds = qty * price
        fee = proceeds * self.fee
        s["cash"] += proceeds - fee
        pnl = proceeds - fee - (s["entry_cost"] + s["entry_fee"])
        s["fees_paid"] += fee
        s["realized_pnl"] += pnl
        ev = {"trade_id": s["trade_id"], "ts": ts, "side": "SELL", "price": price, "qty": qty,
              "value": proceeds, "fee": fee, "pnl": pnl, "reason": reason, "stop": s["stop"],
              "entry_price": s["entry_price"], "entry_ts": s["entry_ts"],
              "return_pct": pnl / (s["entry_cost"] + s["entry_fee"]) * 100}
        s["qty"], s["entry_price"], s["entry_ts"], s["stop"] = 0.0, None, None, None
        s["entry_cost"], s["entry_fee"] = 0.0, 0.0
        if s["qty"] == 0:
            s["cash"] = max(s["cash"], 0.0)
        return ev, f"SELL {qty:.6f} BTC @ {price:.2f}, pnl {pnl:+.2f} USDT ({reason})"

    def on_open(self, ts, o):
        """A new candle just opened at price o: roll the day over and fill any pending order.
        Called by on_bar() in backtests, and straight away by the live loop so fills aren't delayed."""
        s = self.s
        ts, o = int(ts), float(o)
        if s.get("opened_ts") == ts or (s["last_ts"] is not None and ts <= s["last_ts"]):
            return [], []
        events, notes = [], []
        day = self._day(ts)
        if day != s["day"]:
            s["day"] = day
            s["day_start_equity"] = self.equity(o)
            if s["halted_day"] and s["halted_day"] < day:
                notes.append(f"new day {day}: trading resumes")
                s["halted_day"] = None
        p = s["pending"]
        s["pending"] = None
        if p:
            if p["side"] == "buy" and not self.in_position():
                if s["halted_day"]:
                    notes.append("cancelled buy: daily loss limit halt")
                else:
                    ev, msg = self._buy(ts, o, p["stop"], p["reason"])
                    notes.append(msg)
                    if ev:
                        events.append(ev)
            elif p["side"] == "sell" and self.in_position():
                ev, msg = self._sell(ts, o, p["reason"])
                events.append(ev)
                notes.append(msg)
        s["opened_ts"] = ts
        s["open_notes"] = list(notes)
        return events, notes

    # ---------- one closed candle ----------
    def on_bar(self, bar, sig):
        """bar: dict ts, open, high, low, close (a CLOSED candle).
        sig: dict enter, exit, stop, trail_stop (optional), note — computed from candles <= this one.
        Returns (trade_events, decision) where decision = {ts, action, reason, equity, price}."""
        s = self.s
        ts, o, h, l, c = int(bar["ts"]), float(bar["open"]), float(bar["high"]), float(bar["low"]), float(bar["close"])
        if s["last_ts"] is not None and ts <= s["last_ts"]:
            return [], None                                  # already processed (restart safety)
        events, notes = [], []

        # 1-2) day rollover + fill the order decided on the previous candle at THIS candle's open.
        # The live loop may already have done this the moment the candle opened (on_open).
        if s.get("opened_ts") == ts:
            notes += s.get("open_notes", [])
        else:
            evs, n2 = self.on_open(ts, o)
            events += evs
            notes += n2
        s["open_notes"] = []
        day = s["day"]

        # 3) stop-loss inside this candle
        if self.in_position() and s["stop"] is not None and l <= s["stop"]:
            fill_ref = min(s["stop"], o)                     # gapped below the stop -> fill at the open
            ev, msg = self._sell(ts, fill_ref, f"stop-loss hit ({s['stop']:.2f})")
            events.append(ev)
            notes.append(msg)

        eq = self.equity(c)
        s["last_close"] = c

        # 4) daily loss limit
        if not s["halted_day"] and eq <= s["day_start_equity"] * (1 - self.daily_limit):
            s["halted_day"] = day
            msg = (f"HALT: equity {eq:.2f} is {100 * (1 - eq / s['day_start_equity']):.2f}% below today's start "
                   f"{s['day_start_equity']:.2f} (limit {self.daily_limit * 100:.1f}%), no new trades until tomorrow")
            if self.in_position():
                s["pending"] = {"side": "sell", "reason": "daily loss limit"}
                msg += "; closing position at next open"
            s["last_ts"] = ts
            return events, {"ts": ts, "action": "HALT", "reason": "; ".join(notes + [msg]), "equity": eq, "price": c}

        # 5) trailing stop ratchets up only
        ts_new = sig.get("trail_stop")
        if self.in_position() and ts_new is not None and math.isfinite(ts_new) and ts_new < c:
            if ts_new > s["stop"]:
                notes.append(f"stop raised {s['stop']:.2f} -> {ts_new:.2f}")
                s["stop"] = ts_new

        # 6) read the signal on this closed candle; act at the next open
        note = sig.get("note") or ""
        if self.in_position():
            if sig.get("exit"):
                s["pending"] = {"side": "sell", "reason": note or "exit signal"}
                action, reason = "SELL_NEXT_OPEN", note or "exit signal"
            else:
                action, reason = "HOLD", note
        else:
            if sig.get("enter"):
                stop = sig.get("stop")
                if s["halted_day"]:
                    action, reason = "SKIP", "entry signal ignored: daily loss limit halt | " + note
                elif stop is None or not math.isfinite(stop) or stop >= c:
                    action, reason = "SKIP", "entry signal ignored: no valid stop-loss | " + note
                else:
                    s["pending"] = {"side": "buy", "stop": float(stop), "reason": note or "entry signal"}
                    action, reason = "BUY_NEXT_OPEN", f"{note} | stop {stop:.2f}"
            else:
                action = "HALTED" if s["halted_day"] else "WAIT"
                reason = ("exit condition true but nothing to sell | " + note) if sig.get("exit") else note
        s["last_ts"] = ts
        return events, {"ts": ts, "action": action, "reason": "; ".join(notes + [reason]) if notes else reason,
                        "equity": eq, "price": c}
