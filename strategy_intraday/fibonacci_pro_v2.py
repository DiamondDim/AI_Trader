"""Fibonacci Pro v2.

Структурная Fibonacci-стратегия. Логика V2 сохранена без изменения.
Этот модуль переносится из fibonacci_pro_v2 как отдельная стратегия, чтобы
сравнивать её с legacy Fibonacci Pro.
"""

from datetime import time
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

SESSION_START = time(10, 0)
SESSION_END = time(18, 0)

DEFAULT_LOOKBACK = 100
PIVOT_SPAN = 3
MIN_ADX = 18.0
MIN_ATR_RATIO = 0.50
MAX_ATR_RATIO = 2.50
MIN_BODY_RATIO = 0.40
MAX_EMA_DISTANCE = 0.015
MIN_IMPULSE_ATR = 2.0
MIN_RR = 1.20
SIGNAL_COOLDOWN = 12
MAX_SWING_AGE = 120
FIB_ZONE_LOW = 0.382
FIB_ZONE_HIGH = 0.786


def is_active_session(current_time: Any) -> bool:
    return SESSION_START <= current_time.time() < SESSION_END


def generate_fibonacci_pro_signals(df: pd.DataFrame, lookback: int = DEFAULT_LOOKBACK,
                                   diagnostics: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    stats = _new_diagnostics(len(df) if df is not None else 0)
    if diagnostics is not None:
        diagnostics.clear(); diagnostics.update(stats)
    if df is None or df.empty:
        return []
    required = {"open", "high", "low", "close"}
    if not required.issubset(df.columns):
        _sync_diagnostics(diagnostics, stats); return []
    data = _ensure_indicators(df)
    lookback = max(int(lookback), 30)
    if len(data) <= lookback + PIVOT_SPAN + 5:
        _sync_diagnostics(diagnostics, stats); return []
    signals: List[Dict[str, Any]] = []
    last_signal_index = -SIGNAL_COOLDOWN - 1
    last_impulse: Optional[Tuple[Any, Any, str]] = None
    for i in range(lookback + PIVOT_SPAN + 2, len(data)):
        stats["bars_evaluated"] += 1
        current_time = data.index[i]
        if not is_active_session(current_time):
            stats["rejected_session"] += 1; continue
        if i - last_signal_index <= SIGNAL_COOLDOWN:
            stats["rejected_cooldown"] += 1; continue
        current, previous = data.iloc[i], data.iloc[i - 1]
        if not _valid_indicators(current):
            stats["rejected_indicators"] += 1; continue
        atr, atr_avg = float(current["atr_14"]), float(current["atr_50"])
        atr_ratio = atr / atr_avg if atr_avg > 0 else 0.0
        stats["atr_ratio_sum"] += atr_ratio
        if not MIN_ATR_RATIO <= atr_ratio <= MAX_ATR_RATIO:
            stats["rejected_volatility"] += 1; continue
        adx = float(current["adx_14"])
        if adx < MIN_ADX:
            stats["rejected_volatility"] += 1; continue
        ema50, ema200, close = float(current["ema_50"]), float(current["ema_200"]), float(current["close"])
        ema_slope = ema50 - float(data.iloc[i - 5]["ema_50"])
        if ema50 <= 0 or abs(close - ema50) / ema50 > MAX_EMA_DISTANCE:
            stats["rejected_trend"] += 1; continue
        direction = None
        if close > ema50 > ema200 and ema_slope > 0: direction = "bullish"
        elif close < ema50 < ema200 and ema_slope < 0: direction = "bearish"
        else:
            stats["rejected_trend"] += 1; continue
        pivots = _confirmed_pivots(data, i, lookback, PIVOT_SPAN)
        structure = _find_structure(pivots, direction)
        if structure is None:
            stats["rejected_structure"] += 1; continue
        swing_high, swing_low, high_idx, low_idx = structure
        if not _valid_impulse_age(data, i, high_idx, low_idx):
            stats["rejected_impulse"] += 1; continue
        range_size = swing_high - swing_low
        if range_size <= 0 or range_size < atr * MIN_IMPULSE_ATR:
            stats["rejected_impulse"] += 1; continue
        fib = _calculate_fibonacci_levels(swing_high, swing_low)
        zone_low, zone_high = fib["0.382"], fib["0.618"]
        if not _bar_touches_zone(previous, current, zone_low, zone_high, atr * 0.10):
            stats["rejected_fibonacci"] += 1; continue
        candle_range = float(current["high"] - current["low"])
        body = abs(float(current["close"] - current["open"]))
        if candle_range <= 0 or body / candle_range < MIN_BODY_RATIO:
            stats["rejected_confirmation"] += 1; continue
        if direction == "bullish":
            confirmed = (current["close"] > current["open"] and current["close"] > previous["close"]
                         and current["close"] >= zone_low - atr * 0.10 and float(current["low"]) <= zone_high + atr * 0.10)
            momentum_ok = float(current.get("stoch_k", 50.0)) <= 70.0
        else:
            confirmed = (current["close"] < current["open"] and current["close"] < previous["close"]
                         and current["close"] <= zone_high + atr * 0.10 and float(current["high"]) >= zone_low - atr * 0.10)
            momentum_ok = float(current.get("stoch_k", 50.0)) >= 30.0
        if not confirmed:
            stats["rejected_confirmation"] += 1; continue
        if not momentum_ok:
            stats["rejected_momentum"] += 1; continue
        entry = float(data.iloc[min(i + 1, len(data) - 1)]["open"])
        if direction == "bullish": sl, target = swing_low - atr * 0.25, swing_high
        else: sl, target = swing_high + atr * 0.25, swing_low
        risk, reward = abs(entry - sl), abs(target - entry)
        rr = reward / risk if risk > 0 else 0.0
        if rr < MIN_RR:
            stats["rejected_rr"] += 1; continue
        impulse_key = (high_idx, low_idx, direction)
        if impulse_key == last_impulse:
            stats["rejected_duplicate_swing"] += 1; continue
        signals.append({"index": i, "type": direction, "time": current_time,
                        "pattern_name": "Fibonacci_Pro_v2_Long" if direction == "bullish" else "Fibonacci_Pro_v2_Short",
                        "fib_level": _nearest_fib_level(close, fib), "swing_high": swing_high, "swing_low": swing_low,
                        "swing_high_index": high_idx, "swing_low_index": low_idx, "adx": round(adx, 2),
                        "atr_ratio": round(atr_ratio, 3), "rr": round(rr, 3),
                        "diagnostics": {"trend": direction, "zone": [round(zone_low, 8), round(zone_high, 8)],
                                        "impulse_size_atr": round(range_size / atr, 3)}})
        stats["final_signals"] += 1; stats["long_signals" if direction == "bullish" else "short_signals"] += 1
        last_signal_index, last_impulse = i, impulse_key
    _sync_diagnostics(diagnostics, stats)
    return signals


def analyze_fibonacci_pro_signals(df: pd.DataFrame, lookback: int = DEFAULT_LOOKBACK) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    diagnostics: Dict[str, Any] = {}
    return generate_fibonacci_pro_signals(df, lookback=lookback, diagnostics=diagnostics), diagnostics


def _new_diagnostics(bars: int) -> Dict[str, Any]:
    return {"bars_input": bars, "bars_evaluated": 0, "rejected_session": 0, "rejected_indicators": 0,
            "rejected_volatility": 0, "rejected_trend": 0, "rejected_structure": 0, "rejected_impulse": 0,
            "rejected_fibonacci": 0, "rejected_confirmation": 0, "rejected_momentum": 0, "rejected_rr": 0,
            "rejected_duplicate_swing": 0, "rejected_cooldown": 0, "final_signals": 0, "long_signals": 0,
            "short_signals": 0, "atr_ratio_sum": 0.0, "avg_atr_ratio": 0.0}


def _sync_diagnostics(target: Optional[Dict[str, Any]], stats: Dict[str, Any]) -> None:
    if stats["bars_evaluated"]: stats["avg_atr_ratio"] = round(stats["atr_ratio_sum"] / stats["bars_evaluated"], 4)
    stats.pop("atr_ratio_sum", None)
    if target is not None: target.clear(); target.update(stats)


def _valid_indicators(row: pd.Series) -> bool:
    return not any(pd.isna(row.get(name)) for name in ("ema_50", "ema_200", "atr_14", "atr_50", "adx_14", "stoch_k"))


def _confirmed_pivots(df: pd.DataFrame, current_idx: int, lookback: int, span: int) -> List[Tuple[int, str, float]]:
    start, end = max(span, current_idx - lookback), current_idx - span
    pivots = []
    for j in range(start, end + 1):
        left, right = df.iloc[j - span:j], df.iloc[j + 1:j + span + 1]
        if len(left) < span or len(right) < span: continue
        high, low = float(df.iloc[j]["high"]), float(df.iloc[j]["low"])
        if high > float(left["high"].max()) and high >= float(right["high"].max()): pivots.append((j, "H", high))
        elif low < float(left["low"].min()) and low <= float(right["low"].min()): pivots.append((j, "L", low))
    return pivots


def _find_structure(pivots: List[Tuple[int, str, float]], direction: str) -> Optional[Tuple[float, float, int, int]]:
    if len(pivots) < 4: return None
    for k in range(len(pivots) - 4, -1, -1):
        seq = pivots[k:k + 4]; types = [p[1] for p in seq]
        if direction == "bullish" and types == ["L", "H", "L", "H"]:
            l1, h1, l2, h2 = seq
            if l2[2] > l1[2] and h2[2] > h1[2]: return h2[2], l2[2], h2[0], l2[0]
        if direction == "bearish" and types == ["H", "L", "H", "L"]:
            h1, l1, h2, l2 = seq
            if h2[2] < h1[2] and l2[2] < l1[2]: return h2[2], l2[2], h2[0], l2[0]
    return None


def _valid_impulse_age(df: pd.DataFrame, current_idx: int, high_idx: int, low_idx: int) -> bool:
    endpoint = max(high_idx, low_idx)
    return 0 < current_idx - endpoint <= MAX_SWING_AGE


def _calculate_fibonacci_levels(swing_high: float, swing_low: float) -> Dict[str, float]:
    size = swing_high - swing_low
    return {"0.0": swing_low, "0.236": swing_low + size * 0.236, "0.382": swing_low + size * 0.382,
            "0.5": swing_low + size * 0.5, "0.618": swing_low + size * 0.618, "0.786": swing_low + size * 0.786, "1.0": swing_high}


def _nearest_fib_level(price: float, fib: Dict[str, float]) -> float:
    candidates = ("0.382", "0.5", "0.618")
    return float(min(candidates, key=lambda name: abs(price - fib[name])))


def _bar_touches_zone(previous: pd.Series, current: pd.Series, zone_low: float, zone_high: float, buffer: float) -> bool:
    lower, upper = zone_low - buffer, zone_high + buffer
    return any(float(bar["high"]) >= lower and float(bar["low"]) <= upper for bar in (previous, current))


def _ensure_indicators(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()
    if "ema_50" not in result: result["ema_50"] = result["close"].ewm(span=50, adjust=False).mean()
    if "ema_200" not in result: result["ema_200"] = result["close"].ewm(span=200, adjust=False).mean()
    if "atr_14" not in result: result["atr_14"] = _calculate_atr(result, 14)
    if "atr_50" not in result: result["atr_50"] = result["atr_14"].rolling(50, min_periods=20).mean()
    if "stoch_k" not in result:
        low14, high14 = result["low"].rolling(14).min(), result["high"].rolling(14).max()
        result["stoch_k"] = (100 * (result["close"] - low14) / (high14 - low14).replace(0, 1e-10)).rolling(3).mean()
    if "adx_14" not in result: result["adx_14"] = _calculate_adx(result, 14)
    return result


def _calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    tr = pd.concat([df["high"] - df["low"], (df["high"] - df["close"].shift(1)).abs(), (df["low"] - df["close"].shift(1)).abs()], axis=1).max(axis=1)
    return tr.ewm(span=period, adjust=False).mean()


def _calculate_adx(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high, low, close = df["high"], df["low"], df["close"]
    up_move, down_move = high.diff(), -low.diff()
    plus_dm = up_move.where((up_move > 0) & (up_move > down_move), 0.0)
    minus_dm = down_move.where((down_move > 0) & (down_move > up_move), 0.0)
    tr = pd.concat([high - low, (high - close.shift(1)).abs(), (low - close.shift(1)).abs()], axis=1).max(axis=1)
    atr = tr.ewm(span=period, adjust=False).mean().replace(0, pd.NA)
    plus_di = 100 * plus_dm.ewm(span=period, adjust=False).mean() / atr
    minus_di = 100 * minus_dm.ewm(span=period, adjust=False).mean() / atr
    denominator = (plus_di + minus_di).replace(0, pd.NA)
    return (100 * (plus_di - minus_di).abs() / denominator).ewm(span=period, adjust=False).mean()
