"""Unified local cache for MT5 market history."""
from __future__ import annotations

from pathlib import Path
from typing import Optional
import pandas as pd
from utils.logger import LoggingMixin

CACHE_DIR = "cache"
CACHE_EXPIRY_HOURS = 24
CACHE_VERSION = "msk_v2"


class DataCache(LoggingMixin):
    def __init__(self, cache_dir: str | Path | None = None, ttl_hours: float = CACHE_EXPIRY_HOURS):
        super().__init__()
        root = Path(__file__).resolve().parent.parent
        self.cache_dir = Path(cache_dir) if cache_dir else root / CACHE_DIR
        self.ttl_seconds = float(ttl_hours) * 3600.0
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, symbol: str, timeframe: str, bars: int) -> Path:
        safe = str(symbol).replace("/", "_").replace("\\", "_")
        return self.cache_dir / f"{CACHE_VERSION}_{safe}_{str(timeframe).upper()}_{int(bars)}.pkl"

    def _get_cache_path(self, symbol: str, timeframe: str, bars: int) -> str:
        return str(self._path(symbol, timeframe, bars))

    def _is_cache_valid(self, cache_path: str | Path) -> bool:
        path = Path(cache_path)
        if not path.exists(): return False
        if self.ttl_seconds < 0: return True
        return (pd.Timestamp.now().timestamp() - path.stat().st_mtime) <= self.ttl_seconds

    def load(self, symbol: str, timeframe: str, bars: int) -> Optional[pd.DataFrame]:
        path = self._path(symbol, timeframe, bars)
        if not self._is_cache_valid(path): return None
        try:
            data = pd.read_pickle(path)
            if isinstance(data, pd.DataFrame) and not data.empty:
                self.log_info(f"[CACHE] hit: {symbol} {timeframe} ({bars} bars)")
                return data.copy()
        except Exception as exc:
            self.log_warning(f"Ошибка чтения кэша: {exc}")
        return None

    def get(self, symbol: str, timeframe: str, bars: int) -> Optional[pd.DataFrame]:
        return self.load(symbol, timeframe, bars)

    def save(self, symbol: str, timeframe: str, bars: int, data: pd.DataFrame) -> None:
        if data is None or data.empty: return
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            data.to_pickle(self._path(symbol, timeframe, bars))
            self.log_info(f"[CACHE] saved: {symbol} {timeframe} ({bars} bars)")
        except Exception as exc:
            self.log_warning(f"Ошибка записи кэша: {exc}")

    def clear(self) -> None:
        for path in self.cache_dir.glob("*.pkl"):
            try: path.unlink(missing_ok=True)
            except OSError: pass
        self.log_info("[CACHE] cleared")


_cache: DataCache | None = None


def get_data_cache() -> DataCache:
    global _cache
    if _cache is None: _cache = DataCache()
    return _cache
