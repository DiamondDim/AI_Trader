import pandas as pd
from datetime import time
from typing import List, Dict, Any

# Активная торговая сессия (МСК)
# Лондон: 10:00 - 13:00 МСК
# Нью-Йорк: 15:30 - 18:00 МСК
# Мы торгуем в оба окна, но НЕ в мертвую зону 13:00-15:30
SESSION_START = time(10, 0)  # 10:00 МСК
SESSION_END = time(18, 0)  # 18:00 МСК
DEAD_ZONE_START = time(13, 0)  # 13:00 МСК (начало мертвой зоны)
DEAD_ZONE_END = time(15, 30)  # 15:30 МСК (конец мертвой зоны)


def is_active_session(current_time) -> bool:
    """
    Проверяет, находится ли текущее время в активной торговой сессии.
    Торгуем: 10:00-13:00 (Лондон) и 15:30-18:00 (Нью-Йорк)
    НЕ торгуем: 13:00-15:30 (мертвая зона)
    """
    trade_time = current_time.time()

    # Проверяем, что мы в общем окне активности
    if not (SESSION_START <= trade_time < SESSION_END):
        return False

    # Проверяем, что мы НЕ в мертвой зоне
    if DEAD_ZONE_START <= trade_time < DEAD_ZONE_END:
        return False

    return True


def generate_ema_pullback_signals(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """
    Улучшенная стратегия: Откат к EMA(50) с подтверждением разворота Stochastic.
    С фильтром активной торговой сессии.
    """
    signals = []

    # Гарантируем наличие индикаторов
    df = _ensure_indicators(df)

    for i in range(2, len(df)):
        current = df.iloc[i]
        current_time = df.index[i]

        # === НОВЫЙ ФИЛЬТР: Торгуем только в активную сессию ===
        if not is_active_session(current_time):
            continue
        # ========================================================

        prev = df.iloc[i - 1]
        ema_50 = current['ema_50']
        adx = current['adx_14']
        stoch_k = current['stoch_k']
        stoch_d = current.get('stoch_d', stoch_k)

        # Фильтр: сильный тренд
        if adx < 20:
            continue

        # === ЛОНГ ===
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

        # === ШОРТ ===
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
    """Расчет всех необходимых индикаторов"""
    res = df.copy()

    if 'ema_50' not in res.columns:
        res['ema_50'] = res['close'].ewm(span=50, adjust=False).mean()

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

        tr = pd.concat([res['high'] - res['low'], (res['high'] - res['close'].shift()).abs(),
                        (res['low'] - res['close'].shift()).abs()], axis=1).max(axis=1)
        atr = tr.rolling(window=14).mean()

        pos_di = 100 * (pos_dm.rolling(window=14).mean() / atr)
        neg_di = 100 * (neg_dm.rolling(window=14).mean() / atr)

        dx = 100 * (pos_di - neg_di).abs() / (pos_di + neg_di)
        res['adx_14'] = dx.rolling(window=14).mean()

    if 'atr_14' not in res.columns:
        tr = pd.concat([res['high'] - res['low'], (res['high'] - res['close'].shift()).abs(),
                        (res['low'] - res['close'].shift()).abs()], axis=1).max(axis=1)
        res['atr_14'] = tr.rolling(window=14).mean()

    return res
