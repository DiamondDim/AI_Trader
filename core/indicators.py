import numpy as np
import pandas as pd
from utils.logger import LoggingMixin


class Indicators(LoggingMixin):
    """Technical indicators used by all strategies."""

    def __init__(self):
        super().__init__()

    def add_ema(self, df: pd.DataFrame, period: int = 50,
                column_name: str | None = None) -> pd.DataFrame:
        column_name = column_name or f"ema_{period}"
        df[column_name] = df['close'].ewm(span=period, adjust=False).mean()
        self.log_debug(f"Added {column_name} with period {period}")
        return df

    def add_atr(self, df: pd.DataFrame, period: int = 14,
                column_name: str | None = None) -> pd.DataFrame:
        column_name = column_name or f"atr_{period}"
        high, low, close = df['high'], df['low'], df['close']
        tr1 = high - low
        tr2 = (high - close.shift(1)).abs()
        tr3 = (low - close.shift(1)).abs()
        true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        df[column_name] = true_range.ewm(span=period, adjust=False).mean()
        self.log_debug(f"Added {column_name} with period {period}")
        return df

    def add_stochastic(self, df: pd.DataFrame, k_period: int = 14,
                       d_period: int = 3, smooth: int = 3) -> pd.DataFrame:
        low_min = df['low'].rolling(window=k_period).min()
        high_max = df['high'].rolling(window=k_period).max()
        range_hl = (high_max - low_min).replace(0, 1e-10)
        k_fast = 100 * (df['close'] - low_min) / range_hl
        df['stoch_k'] = k_fast.rolling(window=smooth).mean()
        df['stoch_d'] = df['stoch_k'].rolling(window=d_period).mean()
        self.log_debug("Added Stochastic Oscillator (stoch_k, stoch_d)")
        return df

    def add_adx(self, df: pd.DataFrame, period: int = 14,
                column_name: str | None = None) -> pd.DataFrame:
        """Add ADX using the project's established EMA smoothing.

        ``adx_14`` is the canonical name; ``adx`` is kept as a compatibility
        alias so existing Swing code continues to work unchanged.
        """
        column_name = column_name or f"adx_{period}"
        high, low, close = df['high'], df['low'], df['close']
        plus_dm = high.diff()
        minus_dm = -low.diff()
        plus_dm = plus_dm.where((plus_dm > 0) & (plus_dm > minus_dm), 0.0)
        minus_dm = minus_dm.where((minus_dm > 0) & (minus_dm > plus_dm), 0.0)

        tr1 = high - low
        tr2 = (high - close.shift(1)).abs()
        tr3 = (low - close.shift(1)).abs()
        true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = true_range.ewm(span=period, adjust=False).mean()

        # Keep the series numeric. pd.NA changes the Series dtype to object and
        # breaks pandas EWM on Python/pandas versions used by the project.
        safe_atr = atr.mask(atr == 0, np.nan)
        plus_di = 100 * plus_dm.ewm(span=period, adjust=False).mean() / safe_atr
        minus_di = 100 * minus_dm.ewm(span=period, adjust=False).mean() / safe_atr
        denominator = (plus_di + minus_di).mask(lambda s: s == 0, np.nan)
        dx = 100 * (plus_di - minus_di).abs() / denominator
        adx = dx.ewm(span=period, adjust=False).mean()

        df[column_name] = adx
        if period == 14:
            df['adx'] = df[column_name]
        self.log_debug(f"Added {column_name} with period {period}")
        return df

    def add_all(self, df: pd.DataFrame, include_ema_200: bool = True) -> pd.DataFrame:
        """Populate the standard indicator set used by strategies."""
        self.add_ema(df, 50)
        if include_ema_200:
            self.add_ema(df, 200)
        self.add_atr(df, 14)
        self.add_stochastic(df, 14, 3, 3)
        self.add_adx(df, 14)
        return df
