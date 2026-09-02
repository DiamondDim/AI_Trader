"""Cache-first market data provider with MT5 fallback."""
from __future__ import annotations

import pandas as pd

from core.data_cache import DataCache, get_data_cache


class MarketDataProvider:
    def __init__(self, connector, cache: DataCache | None = None):
        self.connector = connector
        self.cache = cache or get_data_cache()

    def get_rates(self, symbol: str, timeframe: str, bars: int, *, refresh: bool = False) -> pd.DataFrame:
        if not refresh:
            cached = self.cache.load(symbol, timeframe, bars)
            if cached is not None:
                print(f"[*] History cache hit: {symbol} {timeframe} {bars}")
                return cached.copy()

        print(f"[*] MT5 history request: {symbol} {timeframe} {bars}")
        df = self.connector.get_rates(symbol, timeframe, bars)
        if df is not None and not df.empty:
            try:
                self.cache.save(symbol, timeframe, bars, df)
                print(f"[*] History cached: {symbol} {timeframe} {bars}")
            except OSError as exc:
                print(f"[!] Cache save skipped: {exc}")
        return df
