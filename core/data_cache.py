"""
Кэширование исторических данных для ускорения бэктестов.
"""
import os
import pickle
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional
from utils.logger import LoggingMixin

CACHE_DIR = "cache"
CACHE_EXPIRY_HOURS = 24  # Кэш действителен 24 часа


class DataCache(LoggingMixin):
    """Кэш для исторических данных MT5"""

    def __init__(self, cache_dir: str = CACHE_DIR):
        super().__init__()
        self.cache_dir = cache_dir
        if not os.path.exists(cache_dir):
            os.makedirs(cache_dir)

    def _get_cache_path(self, symbol: str, timeframe: str, bars: int) -> str:
        """Генерирует путь к файлу кэша"""
        filename = f"{symbol}_{timeframe}_{bars}.pkl"
        return os.path.join(self.cache_dir, filename)

    def _is_cache_valid(self, cache_path: str) -> bool:
        """Проверяет, не истек ли срок годности кэша"""
        if not os.path.exists(cache_path):
            return False

        file_age = datetime.now() - datetime.fromtimestamp(os.path.getmtime(cache_path))
        return file_age < timedelta(hours=CACHE_EXPIRY_HOURS)

    def get(self, symbol: str, timeframe: str, bars: int) -> Optional[pd.DataFrame]:
        """Получить данные из кэша"""
        cache_path = self._get_cache_path(symbol, timeframe, bars)

        if self._is_cache_valid(cache_path):
            try:
                with open(cache_path, 'rb') as f:
                    df = pickle.load(f)
                self.log_info(f"✅ Кэш命中: {symbol} {timeframe} ({bars} баров)")
                return df
            except Exception as e:
                self.log_warning(f"Ошибка чтения кэша: {e}")

        return None

    def save(self, symbol: str, timeframe: str, bars: int, df: pd.DataFrame):
        """Сохранить данные в кэш"""
        cache_path = self._get_cache_path(symbol, timeframe, bars)

        try:
            with open(cache_path, 'wb') as f:
                pickle.dump(df, f)
            self.log_info(f"💾 Сохранено в кэш: {symbol} {timeframe} ({bars} баров)")
        except Exception as e:
            self.log_warning(f"Ошибка записи кэша: {e}")

    def clear(self):
        """Очистить весь кэш"""
        if os.path.exists(self.cache_dir):
            for filename in os.listdir(self.cache_dir):
                if filename.endswith('.pkl'):
                    os.remove(os.path.join(self.cache_dir, filename))
            self.log_info("🗑️ Кэш очищен")


# Глобальный экземпляр
_cache = None


def get_data_cache() -> DataCache:
    global _cache
    if _cache is None:
        _cache = DataCache()
    return _cache
