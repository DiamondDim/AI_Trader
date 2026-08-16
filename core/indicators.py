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

    def add_stochastic(self, df: pd.DataFrame, k_period: int = 14, d_period: int = 3, smooth: int = 3) -> pd.DataFrame:
        """Добавляет Stochastic Oscillator (%K и %D)."""
        low_min = df['low'].rolling(window=k_period).min()
        high_max = df['high'].rolling(window=k_period).max()

        # Избегаем деления на ноль
        range_hl = high_max - low_min
        range_hl = range_hl.replace(0, 1e-10)

        k_fast = 100 * (df['close'] - low_min) / range_hl
        df['stoch_k'] = k_fast.rolling(window=smooth).mean()
        df['stoch_d'] = df['stoch_k'].rolling(window=d_period).mean()

        self.log_debug("Added Stochastic Oscillator (stoch_k, stoch_d)")
        return df

    def add_adx(self, df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
        """Добавляет ADX (Average Directional Index) для оценки силы тренда."""
        high = df['high']
        low = df['low']
        close = df['close']

        plus_dm = high.diff()
        minus_dm = -low.diff()
        plus_dm = plus_dm.where((plus_dm > 0) & (plus_dm > minus_dm), 0)
        minus_dm = minus_dm.where((minus_dm > 0) & (minus_dm > plus_dm), 0)

        tr1 = high - low
        tr2 = (high - close.shift(1)).abs()
        tr3 = (low - close.shift(1)).abs()
        true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

        atr = true_range.ewm(span=period, adjust=False).mean()

        plus_di = 100 * (plus_dm.ewm(span=period, adjust=False).mean() / atr)
        minus_di = 100 * (minus_dm.ewm(span=period, adjust=False).mean() / atr)

        dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di)
        df['adx'] = dx.ewm(span=period, adjust=False).mean()

        self.log_debug(f"Added ADX with period {period}")
        return df
