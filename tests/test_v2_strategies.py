"""The V2 strategies only use completed candles/days (no look-ahead), checked on long 4h history."""
import unittest

import numpy as np
import pandas as pd

from btcpaper.strategies import load
from tests.helpers import synthetic


def four_hour(n=2200, seed=11):
    df = synthetic(n, seed=seed, step_ms=4 * 3_600_000)
    df["ts"] = df["ts"] - df["ts"].iloc[0] % 86_400_000          # align candles to UTC midnight
    df["time"] = pd.to_datetime(df["ts"], unit="ms", utc=True)
    return df


class V2NoLookAhead(unittest.TestCase):
    def test_signals_do_not_change_when_future_candles_are_added(self):
        df = four_hour()
        for name in ("trend_sma200d", "tsmom", "macd_regime", "bb_squeeze"):
            st = load(name)
            full = st.signals(df)
            self.assertTrue(full["enter"].any(), f"{name} never enters on the test data")
            for cut in (1400, 1601, 1799, 2050):
                part = st.signals(df.iloc[:cut].reset_index(drop=True))
                for col in ("enter", "exit"):
                    self.assertTrue((part[col].values == full[col].values[:cut]).all(), f"{name}.{col} looks ahead at {cut}")
                a, b = part["stop"].values, full["stop"].values[:cut]
                self.assertTrue(np.allclose(a, b, equal_nan=True), f"{name}.stop looks ahead at {cut}")

    def test_daily_values_change_only_at_midnight(self):
        df = four_hour()
        out = load("trend_sma200d").signals(df)
        day = df["time"].dt.floor("D")
        per_day = out.groupby(day)["d_sma"].nunique(dropna=False)
        self.assertTrue((per_day <= 1).all())
