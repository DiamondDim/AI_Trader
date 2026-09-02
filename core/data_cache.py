"""Local cache for MT5 market history used by test infrastructure."""
from __future__ import annotations

from pathlib import Path
import pandas as pd


class DataCache:
    def __init__(self, cache_dir: str | Path | None = None, ttl_hours: float = 24.0):
        root = Path(__file__).resolve().parent.parent
        self.cache_dir = Path(cache_dir) if cache_dir else root / "cache"
        self.ttl_seconds = ttl_hours * 3600.0
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, symbol: str, timeframe: str, bars: int) -> Path:
        safe = symbol.replace("/", "_").replace("\\", "_")
        return self.cache_dir / f"{safe}_{timeframe.upper()}_{int(bars)}.pkl"

    def load(self, symbol: str, timeframe: str, bars: int) -> pd.DataFrame | None:
        path = self._path(symbol, timeframe, bars)
        if not path.exists():
            return None
        try:
            if self.ttl_seconds >= 0 and (pd.Timestamp.now().timestamp() - path.stat().st_mtime) > self.ttl_seconds:
                return None
            data = pd.read_pickle(path)
            return data if isinstance(data, pd.DataFrame) and not data.empty else None
        except Exception:
            return None

    def save(self, symbol: str, timeframe: str, bars: int, data: pd.DataFrame) -> None:
        if data is None or data.empty:
            return
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        data.to_pickle(self._path(symbol, timeframe, bars))

    def clear(self) -> None:
        for path in self.cache_dir.glob("*.pkl"):
            path.unlink(missing_ok=True)
