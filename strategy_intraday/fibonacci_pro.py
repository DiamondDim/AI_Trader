"""
Fibonacci Pro Strategy (УЖЕСТОЧЁННАЯ ВЕРСИЯ)
Стратегия на основе уровней Фибоначчи с динамическими зонами входа.
Добавлены: фильтр силы свечи, ужесточённый ADX, фильтр волатильности.
"""
import pandas as pd
from datetime import time
from typing import List, Dict, Any, Tuple

SESSION_START = time(10, 0)
SESSION_END = time(18, 0)
DEAD_ZONE_START = time(13, 0)
DEAD_ZONE_END = time(15, 30)


def is_active_session(current_time) -> bool:
    trade_time = current_time.time()
    if not (SESSION_START <= trade_time < SESSION_END):
        return False
    if DEAD_ZONE_START <= trade_time < DEAD_ZONE_END:
        return False
    return True


def generate_fibonacci_pro_signals(df: pd.DataFrame, lookback: int = 30) -> List[Dict[str, Any]]:
    signals = []
    df = _ensure_indicators(df)

    if 'atr_50_avg' not in df.columns:
        df['atr_50_avg'] = df['atr_14'].rolling(window=50).mean()

    for i in range(lookback + 2, len(df)):
        current = df.iloc[i]
        current_time = df.index[i]

        if not is_active_session(current_time):
            continue
        if current['adx_14'] < 25:
            continue

        atr_current = current['atr_14']
        atr_avg = current.get('atr_50_avg', atr_current)
        if atr_current < (atr_avg * 0.5):
            continue

        ema_50 = current['ema_50']
        ema_200 = current.get('ema_200', ema_50)
        distance_from_ema = abs(current['close'] - ema_50) / ema_50
        if distance_from_ema > 0.01:
            continue

        swing_high, swing_low = _find_swing_points(df, i, lookback)
        if swing_high is None or swing_low is None:
            continue
        range_size = swing_high - swing_low
        if range_size == 0:
            continue

        fib_levels = _calculate_fibonacci_levels(swing_high, swing_low)
        current_price = current['close']

        body_size = abs(current['close'] - current['open'])
        candle_range = current['high'] - current['low']
        if candle_range == 0 or (body_size / candle_range) < 0.5:
            continue

        if current_price > ema_50 and ema_50 > ema_200:
            for fib_level_name, fib_price in fib_levels.items():
                if fib_level_name in ['0.236', '0.382', '0.5']:
                    if _is_bounce_above_level(df, i, fib_price, tolerance=0.0005):
                        if current['stoch_k'] < 30:
                            signals.append({
                                'index': i,
                                'type': 'bullish',
                                'time': current_time,
                                'pattern_name': f'Fibonacci_Pro_Long_{fib_level_name}',
                                'fib_level': float(fib_level_name),
                                'swing_high': swing_high,
                                'swing_low': swing_low
                            })
                            break
        elif current_price < ema_50 and ema_50 < ema_200:
            for fib_level_name, fib_price in fib_levels.items():
                if fib_level_name in ['0.618', '0.786', '0.764']:
                    if _is_bounce_below_level(df, i, fib_price, tolerance=0.0005):
                        if current['stoch_k'] > 70:
                            signals.append({
                                'index': i,
                                'type': 'bearish',
                                'time': current_time,
                                'pattern_name': f'Fibonacci_Pro_Short_{fib_level_name}',
                                'fib_level': float(fib_level_name),
                                'swing_high': swing_high,
                                'swing_low': swing_low
                            })
                            break
    return signals


def _find_swing_points(df: pd.DataFrame, current_idx: int, lookback: int) -> Tuple[float, float]:
    recent_highs = df['high'].iloc[current_idx - lookback:current_idx]
    recent_lows = df['low'].iloc[current_idx - lookback:current_idx]
    swing_high = recent_highs.max()
    swing_low = recent_lows.min()
    high_idx = recent_highs.idxmax()
    low_idx = recent_lows.idxmin()
    current_idx_abs = df.index[current_idx]
    if high_idx == current_idx_abs or low_idx == current_idx_abs:
        return None, None
    return swing_high, swing_low


def _calculate_fibonacci_levels(swing_high: float, swing_low: float) -> Dict[str, float]:
    range_size = swing_high - swing_low
    return {
        '0.0': swing_low,
        '0.236': swing_low + (range_size * 0.236),
        '0.382': swing_low + (range_size * 0.382),
        '0.5': swing_low + (range_size * 0.5),
        '0.618': swing_low + (range_size * 0.618),
        '0.764': swing_low + (range_size * 0.764),
        '0.786': swing_low + (range_size * 0.786),
        '1.0': swing_high
    }


def _is_bounce_above_level(df: pd.DataFrame, current_idx: int, level: float, tolerance: float) -> bool:
    current = df.iloc[current_idx]
    prev = df.iloc[current_idx - 1]
    min_price = min(current['low'], prev['low'])
    distance_to_level = abs(min_price - level) / level
    return distance_to_level <= tolerance and current['close'] > level


def _is_bounce_below_level(df: pd.DataFrame, current_idx: int, level: float, tolerance: float) -> bool:
    current = df.iloc[current_idx]
    prev = df.iloc[current_idx - 1]
    max_price = max(current['high'], prev['high'])
    distance_to_level = abs(max_price - level) / level
    return distance_to_level <= tolerance and current['close'] < level


def _ensure_indicators(df: pd.DataFrame) -> pd.DataFrame:
    res = df.copy()
    if 'ema_50' not in res.columns:
        res['ema_50'] = res['close'].ewm(span=50, adjust=False).mean()
    if 'ema_200' not in res.columns:
        res['ema_200'] = res['close'].ewm(span=200, adjust=False).mean()
    if 'stoch_k' not in res.columns:
        low_14 = res['low'].rolling(window=14).min()
        high_14 = res['high'].rolling(window=14).max()
        raw_k = 100 * (res['close'] - low_14) / (high_14 - low_14)
        res['stoch_k'] = raw_k.rolling(window=3).mean()
        res['stoch_d'] = res['stoch_k'].rolling(window=3).mean()
    if 'adx_14' not in res.columns:
        up_move = res['high'] - res['high'].shift(1)
        down_move = res['low'].shift(1) - res['low']
        pos_dm = ((up_move > down_move) & (up_move > 0)) * up_move
        neg_dm = ((down_move > up_move) & (down_move > 0)) * down_move
        tr = pd.concat([
            res['high'] - res['low'],
            (res['high'] - res['close'].shift()).abs(),
            (res['low'] - res['close'].shift()).abs()
        ], axis=1).max(axis=1)
        atr = tr.rolling(window=14).mean()
        pos_di = 100 * (pos_dm.rolling(window=14).mean() / atr)
        neg_di = 100 * (neg_dm.rolling(window=14).mean() / atr)
        dx = 100 * (pos_di - neg_di).abs() / (pos_di + neg_di)
        res['adx_14'] = dx.rolling(window=14).mean()
    if 'atr_14' not in res.columns:
        tr = pd.concat([
            res['high'] - res['low'],
            (res['high'] - res['close'].shift()).abs(),
            (res['low'] - res['close'].shift()).abs()
        ], axis=1).max(axis=1)
        res['atr_14'] = tr.rolling(window=14).mean()
    return res
