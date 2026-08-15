import pandas as pd
from utils.logger import LoggingMixin


class Indicators(LoggingMixin):
    """Класс для расчета технических индикаторов."""

    def __init__(self):
        super().__init__()

    def add_ema(self, df: pd.DataFrame, period: int = 50, column_name: str = 'ema_50') -> pd.DataFrame:
        """Добавляет EMA (Exponential Moving Average) в DataFrame."""
        df[column_name] = df['close'].ewm(span=period, adjust=False).mean()
        self.log_debug(f"Added {column_name} with period {period}")
        return df

    def add_atr(self, df: pd.DataFrame, period: int = 14, column_name: str = 'atr_14') -> pd.DataFrame:
        """
        Добавляет ATR (Average True Range) — индикатор волатильности.
        Используется для динамического расчета Stop Loss.
        """
        high = df['high']
        low = df['low']
        close = df['close']

        # True Range = максимум из:
        # 1. High - Low
        # 2. |High - Previous Close|
        # 3. |Low - Previous Close|
        tr1 = high - low
        tr2 = (high - close.shift(1)).abs()
        tr3 = (low - close.shift(1)).abs()

        true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

        # ATR = EMA от True Range
        df[column_name] = true_range.ewm(span=period, adjust=False).mean()
        self.log_debug(f"Added {column_name} with period {period}")
        return df
