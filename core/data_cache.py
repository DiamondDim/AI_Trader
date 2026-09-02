"""Local OHLCV cache for repeatable MT5 backtests.

The cache is deliberately independent from the broker connector. It stores
DataFrames locally and never contains credentials or trading state.
"""
from __future__ import annotations

from pathlib import Path
import time
from typing import Optional

import pandas as pd


DEFAULT_CACHE_DIR = Path(__file__).resolve().parent.parent / "cache"
DEFAULT_TTL_SECONDS = 24 * 60 * 60


class DataCache:
    def __init__(self, cache_dir: Path | str = DEFAULT_CACHE_DIR, ttl_seconds: int = DEFAULT_TTL_SECONDS):
        self.cache_dir = Path(cache_dir)
        self.ttl_seconds = int(ttl_seconds)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _safe_symbol(symbol: str) -> str:
        return "".join(ch for ch in str(symbol) if ch.isalnum() or ch in "_-.")

    def path(self, symbol: str, timeframe: str, bars: int) -> Path:
        return self.cache_dir / f"{self._safe_symbol(symbol)}_{str(timeframe).upper()}_{int(bars)}.pkl"

    def load(self, symbol: str, timeframe: str, bars: int, *, allow_stale: bool = False) -> Optional[pd.DataFrame]:
        path = self.path(symbol, timeframe, bars)
        if not path.is_file():
            return None
        if not allow_stale and self.ttl_seconds > 0 and time.time() - path.stat().st_mtime > self.ttl_seconds:
            return None
        try:
            df = pd.read_pickle(path)
            return df if isinstance(df, pd.DataFrame) and not df.empty else None
        except Exception:
            return None

    def save(self, symbol: str, timeframe: str, bars: int, df: pd.DataFrame) -> Path:
        path = self.path(symbol, timeframe, bars)
        df.to_pickle(path)
        return path

    def clear(self) -> int:
        count = 0
        for path in self.cache_dir.glob("*.pkl"):
            try:
                path.unlink(); count += 1
            except OSError:
                pass
        return count


_cache = DataCache()


def get_data_cache() -> DataCache:
    return _cache
