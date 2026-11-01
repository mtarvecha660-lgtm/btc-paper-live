import unittest

from btcpaper import data as D


class Fallback(unittest.TestCase):
    def test_next_source_used_when_first_is_blocked(self):
        saved = dict(D.FETCHERS)
        step = 60_000
        now = D._now_ms() // step * step

        def blocked(*a):
            raise D.DataError("HTTP 451: Service unavailable from a restricted location")

        def ok(symbol, tf, since, until):
            return [[t, 1.0, 2.0, 0.5, 1.5, 10.0] for t in range(since, min(until, now - step) + 1, step)]
        try:
            D.FETCHERS["binance"] = blocked
            D.FETCHERS["okx"] = ok
            df, src = D.fetch("BTC/USDT", "1m", now - 100 * step, now, ["binance", "okx"], verbose=False, use_cache=False)
            self.assertEqual(src, "okx")
            self.assertGreater(len(df), 90)
            self.assertTrue((df["ts"] + step <= D._now_ms()).all())     # no unfinished candle
        finally:
            D.FETCHERS.clear()
            D.FETCHERS.update(saved)

    def test_all_sources_fail_raises(self):
        saved = dict(D.FETCHERS)
        try:
            D.FETCHERS["binance"] = lambda *a: (_ for _ in ()).throw(D.DataError("blocked"))
            with self.assertRaises(D.DataError):
                D.fetch("BTC/USDT", "1m", D._now_ms() - 3_600_000, None, ["binance"], verbose=False, use_cache=False)
        finally:
            D.FETCHERS.clear()
            D.FETCHERS.update(saved)

    def test_inr_grouping(self):
        from btcpaper.money import inr_group
        self.assertEqual(inr_group(500000), "5,00,000.00")
        self.assertEqual(inr_group(7417970.68), "74,17,970.68")
        self.assertEqual(inr_group(-1234.5), "-1,234.50")


if __name__ == "__main__":
    unittest.main()
