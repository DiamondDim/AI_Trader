"""
Fibonacci Pro — redesigned trend/pullback strategy.

Основная идея:
    1. Определяем направленный рынок по EMA 50/200 и наклону EMA 50.
    2. Находим подтвержденный swing range только по уже закрытым барам.
    3. Ждем откат в рабочую Fibonacci-зону 0.382–0.618.
    4. Требуем подтверждение возврата цены в сторону тренда.
    5. Фильтруем слабые/неактивные условия через ADX, ATR и размер свечи.

Важно: функция возвращает только сигналы. Вход/SL/TP и размер позиции
остаются ответственностью общего Backtester, чтобы стратегия была полностью
совместима с существующим test runner.
"""

from datetime import time
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd


# Торговое окно оставлено совместимым с прежней версией, но dead zone убрана:
# сама стратегия уже достаточно фильтрует качество входов.
SESSION_START = time(10, 0)
SESSION_END = time(18, 0)

# Параметры стратегии.
DEFAULT_LOOKBACK = 48
MIN_ADX = 18.0
MAX_ATR_RATIO = 2.5
MIN_ATR_RATIO = 0.55
MIN_BODY_RATIO = 0.45
EMA_DISTANCE_MAX = 0.012
SWING_MIN_ATR = 2.5
SIGNAL_COOLDOWN = 6

# Основная рабочая зона отката. 0.5 — середина диапазона, 0.618 — глубокий
# откат. Допускаем небольшой буфер вокруг зоны через ATR.
FIB_ZONE_LOW = 0.382
FIB_ZONE_HIGH = 0.618


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def is_active_session(current_time) -> bool:
    """Return True when the bar belongs to the configured trading session."""
    trade_time = current_time.time()
    return SESSION_START <= trade_time < SESSION_END


def generate_fibonacci_pro_signals(
    df: pd.DataFrame,
    lookback: int = DEFAULT_LOOKBACK,
) -> List[Dict[str, Any]]:
    """Generate Fibonacci pullback signals without look-ahead bias.

    The existing runner calls this function with only a DataFrame, so the
    public signature intentionally remains unchanged apart from the optional
    lookback argument.
    """
    if df is None or df.empty:
        return []

    required = {"open", "high", "low", "close"}
    if not required.issubset(df.columns):
        return []

    data = _ensure_indicators(df)
    lookback = max(int(lookback), 20)

    if len(data) <= lookback + 5:
        return []

    signals: List[Dict[str, Any]] = []
    last_signal_index = -SIGNAL_COOLDOWN - 1

    for i in range(lookback + 2, len(data)):
        if i - last_signal_index <= SIGNAL_COOLDOWN:
            continue

        current_time = data.index[i]
        if not is_active_session(current_time):
            continue

        current = data.iloc[i]
        previous = data.iloc[i - 1]

        # Indicators must be valid before any comparison.
        indicator_values = [
            current.get("ema_50"),
            current.get("ema_200"),
            current.get("atr_14"),
            current.get("atr_50"),
            current.get("adx_14"),
        ]
        if any(pd.isna(value) for value in indicator_values):
            continue

        atr = float(current["atr_14"])
        atr_avg = float(current["atr_50"])
        if atr <= 0 or atr_avg <= 0:
            continue

        # Избегаем как мертвого рынка, так и экстремального spike-режима.
        atr_ratio = atr / atr_avg
        if atr_ratio < MIN_ATR_RATIO or atr_ratio > MAX_ATR_RATIO:
            continue

        adx = float(current["adx_14"])
        if adx < MIN_ADX:
            continue

        ema50 = float(current["ema_50"])
        ema200 = float(current["ema_200"])
        close = float(current["close"])

        if ema50 <= 0:
            continue

        # Тренд должен быть не только выше/ниже EMA200, но и иметь
        # направленный наклон EMA50. Это существенно уменьшает flat-market
        # сделки, которые были одной из проблем старой версии.
        ema50_prev = float(data.iloc[i - 5]["ema_50"])
        ema50_slope = ema50 - ema50_prev
        if pd.isna(ema50_prev):
            continue

        distance_from_ema50 = abs(close - ema50) / ema50
        if distance_from_ema50 > EMA_DISTANCE_MAX:
            continue

        swing_high, swing_low, high_idx, low_idx = _find_swing_points(
            data, i, lookback
        )
        if swing_high is None or swing_low is None:
            continue

        range_size = swing_high - swing_low
        if range_size <= 0 or range_size < atr * SWING_MIN_ATR:
            continue

        fib = _calculate_fibonacci_levels(swing_high, swing_low)

        # Последняя цена должна находиться около реальной retracement zone.
        # Буфер зависит от ATR, поэтому фиксированное 0.05% больше не является
        # одинаковым для EURUSD, JPY и кроссов.
        zone_buffer = max(atr * 0.20, range_size * 0.015)

        candle_range = float(current["high"] - current["low"])
        body = abs(float(current["close"] - current["open"]))
        if candle_range <= 0 or body / candle_range < MIN_BODY_RATIO:
            continue

        # ---------------------------------------------------------------
        # LONG: восходящий тренд + откат к 38.2–61.8% + bullish rejection
        # ---------------------------------------------------------------
        if close > ema50 > ema200 and ema50_slope > 0:
            zone_low = fib["0.382"]
            zone_high = fib["0.618"]

            touched_zone = _bar_touches_zone(
                previous, current, zone_low, zone_high, zone_buffer
            )
            if not touched_zone:
                continue

            # Подтверждение должно показывать покупателя: текущая свеча
            # закрывается выше предыдущего close и выше/около 38.2%.
            bullish_confirmation = (
                current["close"] > current["open"]
                and current["close"] > previous["close"]
                and current["close"] >= zone_low - zone_buffer
            )
            if not bullish_confirmation:
                continue

            # Stochastic используется как дополнительный context filter, а не
            # как обязательное условие oversold. Старый stoch<30 практически
            # конфликтовал с уже начавшимся bullish reversal.
            stoch_k = current.get("stoch_k")
            stoch_ok = pd.isna(stoch_k) or float(stoch_k) < 65
            if not stoch_ok:
                continue

            signals.append(
                _build_signal(
                    index=i,
                    current_time=current_time,
                    signal_type="bullish",
                    pattern_name="Fibonacci_Pro_Long",
                    fib_level=_nearest_fib_level(close, fib),
                    swing_high=swing_high,
                    swing_low=swing_low,
                    swing_high_index=high_idx,
                    swing_low_index=low_idx,
                    adx=adx,
                    atr_ratio=atr_ratio,
                )
            )
            last_signal_index = i
            continue

        # ---------------------------------------------------------------
        # SHORT: нисходящий тренд + откат к 38.2–61.8% + bearish rejection
        # ---------------------------------------------------------------
        if close < ema50 < ema200 and ema50_slope < 0:
            # Для short retracement считаем от low к high, поэтому рабочая
            # зона симметрично находится между 38.2 и 61.8%.
            zone_low = fib["0.382"]
            zone_high = fib["0.618"]

            touched_zone = _bar_touches_zone(
                previous, current, zone_low, zone_high, zone_buffer
            )
            if not touched_zone:
                continue

            bearish_confirmation = (
                current["close"] < current["open"]
                and current["close"] < previous["close"]
                and current["close"] <= zone_high + zone_buffer
            )
            if not bearish_confirmation:
                continue

            stoch_k = current.get("stoch_k")
            stoch_ok = pd.isna(stoch_k) or float(stoch_k) > 35
            if not stoch_ok:
                continue

            signals.append(
                _build_signal(
                    index=i,
                    current_time=current_time,
                    signal_type="bearish",
                    pattern_name="Fibonacci_Pro_Short",
                    fib_level=_nearest_fib_level(close, fib),
                    swing_high=swing_high,
                    swing_low=swing_low,
                    swing_high_index=high_idx,
                    swing_low_index=low_idx,
                    adx=adx,
                    atr_ratio=atr_ratio,
                )
            )
            last_signal_index = i

    return signals


# ---------------------------------------------------------------------------
# Swing/Fibonacci logic
# ---------------------------------------------------------------------------

def _find_swing_points(
    df: pd.DataFrame,
    current_idx: int,
    lookback: int,
) -> Tuple[Optional[float], Optional[float], Optional[Any], Optional[Any]]:
    """Find the range using only bars before current_idx.

    A simple rolling range is deliberately used instead of a centered pivot,
    because centered pivots would require future bars and introduce look-ahead
    bias into the backtest.
    """
    start = max(0, current_idx - lookback)
    window = df.iloc[start:current_idx]
    if window.empty:
        return None, None, None, None

    high_idx = window["high"].idxmax()
    low_idx = window["low"].idxmin()
    swing_high = float(window.loc[high_idx, "high"])
    swing_low = float(window.loc[low_idx, "low"])

    if swing_high <= swing_low:
        return None, None, None, None

    return swing_high, swing_low, high_idx, low_idx


def _calculate_fibonacci_levels(
    swing_high: float,
    swing_low: float,
) -> Dict[str, float]:
    range_size = swing_high - swing_low
    return {
        "0.0": swing_low,
        "0.236": swing_low + range_size * 0.236,
        "0.382": swing_low + range_size * 0.382,
        "0.5": swing_low + range_size * 0.500,
        "0.618": swing_low + range_size * 0.618,
        "0.786": swing_low + range_size * 0.786,
        "1.0": swing_high,
    }


def _nearest_fib_level(price: float, fib: Dict[str, float]) -> float:
    candidates = ["0.382", "0.5", "0.618"]
    nearest = min(candidates, key=lambda name: abs(price - fib[name]))
    return float(nearest)


def _bar_touches_zone(
    previous: pd.Series,
    current: pd.Series,
    zone_low: float,
    zone_high: float,
    buffer: float,
) -> bool:
    """Return True if either of the last two bars interacted with the zone."""
    lower = zone_low - buffer
    upper = zone_high + buffer

    for bar in (previous, current):
        if float(bar["high"]) >= lower and float(bar["low"]) <= upper:
            return True
    return False


def _build_signal(
    *,
    index: int,
    current_time: Any,
    signal_type: str,
    pattern_name: str,
    fib_level: float,
    swing_high: float,
    swing_low: float,
    swing_high_index: Any,
    swing_low_index: Any,
    adx: float,
    atr_ratio: float,
) -> Dict[str, Any]:
    return {
        "index": index,
        "type": signal_type,
        "time": current_time,
        "pattern_name": pattern_name,
        "fib_level": fib_level,
        "swing_high": swing_high,
        "swing_low": swing_low,
        "swing_high_index": swing_high_index,
        "swing_low_index": swing_low_index,
        "adx": round(adx, 2),
        "atr_ratio": round(atr_ratio, 3),
    }


# ---------------------------------------------------------------------------
# Indicator compatibility layer
# ---------------------------------------------------------------------------

def _ensure_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Ensure indicators required by Fibonacci Pro exist.

    run_intraday_backtest already populates the canonical project indicators.
    These fallbacks keep this module independently usable in tests/fixtures and
    do not overwrite existing project values.
    """
    res = df.copy()

    if "ema_50" not in res.columns:
        res["ema_50"] = res["close"].ewm(span=50, adjust=False).mean()

    if "ema_200" not in res.columns:
        res["ema_200"] = res["close"].ewm(span=200, adjust=False).mean()

    if "atr_14" not in res.columns:
        res["atr_14"] = _calculate_atr(res, 14)

    if "atr_50" not in res.columns:
        res["atr_50"] = res["atr_14"].rolling(window=50, min_periods=20).mean()

    if "stoch_k" not in res.columns:
        low_14 = res["low"].rolling(window=14).min()
        high_14 = res["high"].rolling(window=14).max()
        denominator = (high_14 - low_14).replace(0, 1e-10)
        raw_k = 100 * (res["close"] - low_14) / denominator
        res["stoch_k"] = raw_k.rolling(window=3).mean()

    if "adx_14" not in res.columns:
        res["adx_14"] = _calculate_adx(res, 14)

    return res


def _calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    tr = pd.concat(
        [
            df["high"] - df["low"],
            (df["high"] - df["close"].shift(1)).abs(),
            (df["low"] - df["close"].shift(1)).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr.ewm(span=period, adjust=False).mean()


def _calculate_adx(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high = df["high"]
    low = df["low"]
    close = df["close"]

    up_move = high.diff()
    down_move = -low.diff()
    plus_dm = up_move.where((up_move > 0) & (up_move > down_move), 0.0)
    minus_dm = down_move.where((down_move > 0) & (down_move > up_move), 0.0)

    tr = pd.concat(
        [
            high - low,
            (high - close.shift(1)).abs(),
            (low - close.shift(1)).abs(),
        ],
        axis=1,
    ).max(axis=1)

    atr = tr.ewm(span=period, adjust=False).mean().replace(0, float("nan"))
    plus_di = 100 * plus_dm.ewm(span=period, adjust=False).mean() / atr
    minus_di = 100 * minus_dm.ewm(span=period, adjust=False).mean() / atr
    denominator = (plus_di + minus_di).replace(0, float("nan"))
    dx = 100 * (plus_di - minus_di).abs() / denominator
    return dx.ewm(span=period, adjust=False).mean()
