import pandas as pd
from datetime import time
from typing import List, Dict, Any

from core.indicators import Indicators

# Активная торговая сессия (МСК)
# Лондон: 10:00 - 13:00 МСК
# Нью-Йорк: 15:30 - 18:00 МСК
# Мы торгуем в оба окна, но НЕ в мертвую зону 13:00-15:30
SESSION_START = time(10, 0)
SESSION_END = time(18, 0)
DEAD_ZONE_START = time(13, 0)
DEAD_ZONE_END = time(15, 30)


def is_active_session(current_time) -> bool:
    """Проверяет активные торговые окна EMA Pullback в МСК."""
    trade_time = current_time.time()
    if not (SESSION_START <= trade_time < SESSION_END):
        return False
    if DEAD_ZONE_START <= trade_time < DEAD_ZONE_END:
        return False
    return True


def generate_ema_pullback_signals(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """
    Откат к EMA(50) с подтверждением разворота Stochastic и фильтром ADX.
    Торговые условия стратегии не изменены.
    """
    signals = []
    df = _ensure_indicators(df)

    for i in range(2, len(df)):
        current = df.iloc[i]
        current_time = df.index[i]

        if not is_active_session(current_time):
            continue

        prev = df.iloc[i - 1]
        ema_50 = current['ema_50']
        adx = current['adx_14']
        stoch_k = current['stoch_k']
        stoch_d = current.get('stoch_d', stoch_k)

        if adx < 20:
            continue

        distance_to_ema = abs(current['low'] - ema_50) / ema_50

        if (current['close'] > ema_50 and
                distance_to_ema < 0.005 and
                stoch_k < 30 and
                stoch_k > stoch_d and
                prev.get('stoch_k', 50) < prev.get('stoch_d', 50) and
                current['close'] > current['open']):
            signals.append({
                'index': i,
                'type': 'bullish',
                'time': current_time,
                'pattern_name': 'EMA50_Pullback_Long'
            })
            continue

        if (current['close'] < ema_50 and
                distance_to_ema < 0.005 and
                stoch_k > 70 and
                stoch_k < stoch_d and
                prev.get('stoch_k', 50) > prev.get('stoch_d', 50) and
                current['close'] < current['open']):
            signals.append({
                'index': i,
                'type': 'bearish',
                'time': current_time,
                'pattern_name': 'EMA50_Pullback_Short'
            })

    return signals


def _ensure_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Ensure indicators through the shared core implementation.

    Existing columns are preserved; missing canonical indicators are added.
    This keeps the strategy API backward-compatible while eliminating the
    duplicate ADX/ATR implementations that previously lived here.
    """
    res = df.copy()
    indicators = Indicators()

    if 'ema_50' not in res.columns:
        indicators.add_ema(res, 50)
    if 'ema_200' not in res.columns:
        indicators.add_ema(res, 200)
    if 'atr_14' not in res.columns:
        indicators.add_atr(res, 14)
    if 'stoch_k' not in res.columns or 'stoch_d' not in res.columns:
        indicators.add_stochastic(res, 14, 3, 3)
    if 'adx_14' not in res.columns:
        indicators.add_adx(res, 14)

    # Backward compatibility for callers that still expect the legacy name.
    if 'adx' not in res.columns and 'adx_14' in res.columns:
        res['adx'] = res['adx_14']

    return res
