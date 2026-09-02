"""Cache-first market data access for test runners."""
from __future__ import annotations

import pandas as pd

from core.data_cache import DataCache


class MarketDataProvider:
    def __init__(self, connector, cache: DataCache | None = None):
        self.connector = connector
        self.cache = cache or DataCache()

    def get_rates(self, symbol: str, timeframe: str, bars: int = 100, refresh: bool = False) -> pd.DataFrame:
        if not refresh:
            cached = self.cache.load(symbol, timeframe, bars)
            if cached is not None:
                print(f"[CACHE] {symbol} {timeframe} {bars}: hit")
                return cached.copy()

        print(f"[MT5] {symbol} {timeframe} {bars}: request")
        data = self.connector.get_rates(symbol, timeframe, bars)
        if data is None or data.empty:
            return pd.DataFrame()
        self.cache.save(symbol, timeframe, bars, data)
        print(f"[CACHE] {symbol} {timeframe} {bars}: saved")
        return data.copy()
