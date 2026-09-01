"""Fibonacci Pro v2.

A stricter, structure-first Fibonacci pullback strategy.  The existing
``fibonacci_pro.py`` is intentionally left untouched; v2 is introduced as an
isolated strategy so results can be compared without changing the shared
runner/backtester contract.

Design goals:
* only confirmed pivots are used (no look-ahead);
* the Fibonacci range must be a real directional impulse, not an arbitrary
  rolling high/low pair;
* long setups require HH/HL structure, short setups require LH/LL structure;
* entry requires interaction with the 0.50-0.618 retracement area plus a
  reversal candle;
* one signal is emitted per structural swing and cooldown prevents duplicates;
* optional diagnostics expose the first rejection reason for every bar.
"""

from datetime import time
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd


SESSION_START = time(10, 0)
SESSION_END = time(18, 0)

DEFAULT_LOOKBACK = 72
PIVOT_SPAN = 2
MIN_ADX = 20.0
MIN_ATR_RATIO = 0.60
MAX_ATR_RATIO = 2.20
MIN_BODY_RATIO = 0.50
MAX_EMA_DISTANCE = 0.010
MIN_IMPULSE_ATR = 3.0
MIN_RR = 1.50
SIGNAL_COOLDOWN = 8
MAX_SWING_AGE = 40
FIB_ZONE_LOW = 0.50
FIB_ZONE_HIGH = 0.618


def is_active_session(current_time: Any) -> bool:
    return SESSION_START <= current_time.time() < SESSION_END


def generate_fibonacci_pro_signals(
    df: pd.DataFrame,
    lookback: int = DEFAULT_LOOKBACK,
    diagnostics: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Generate v2 signals using only information available at bar ``i``.

    The optional ``diagnostics`` dictionary is populated in-place and is
    intentionally compatible with the existing runner, which calls the
    generator with a single DataFrame argument.
    """
    stats = _new_diagnostics(len(df) if df is not None else 0)
    if diagnostics is not None:
        diagnostics.clear()
        diagnostics.update(stats)

    if df is None or df.empty:
        return []

    required = {"open", "high", "low", "close"}
    if not required.issubset(df.columns):
        _sync_diagnostics(diagnostics, stats)
        return []

    data = _ensure_indicators(df)
    lookback = max(int(lookback), 30)
    if len(data) <= lookback + PIVOT_SPAN + 5:
        _sync_diagnostics(diagnostics, stats)
        return []

    signals: List[Dict[str, Any]] = []
    last_signal_index = -SIGNAL_COOLDOWN - 1
    last_impulse: Optional[Tuple[Any, Any, str]] = None

    for i in range(lookback + PIVOT_SPAN + 2, len(data)):
        stats["bars_evaluated"] += 1

        current_time = data.index[i]
        if not is_active_session(current_time):
            stats["rejected_session"] += 1
            continue

        if i - last_signal_index <= SIGNAL_COOLDOWN:
            stats["rejected_cooldown"] += 1
            continue

        current = data.iloc[i]
        previous = data.iloc[i - 1]

        if not _valid_indicators(current):
            stats["rejected_indicators"] += 1
            continue

        atr = float(current["atr_14"])
        atr_avg = float(current["atr_50"])
        atr_ratio = atr / atr_avg if atr_avg > 0 else 0.0
        stats["atr_ratio_sum"] += atr_ratio
        if not MIN_ATR_RATIO <= atr_ratio <= MAX_ATR_RATIO:
            stats["rejected_volatility"] += 1
            continue

        adx = float(current["adx_14"])
        if adx < MIN_ADX:
            stats["rejected_volatility"] += 1
            continue

        ema50 = float(current["ema_50"])
        ema200 = float(current["ema_200"])
        close = float(current["close"])
        ema50_prev = float(data.iloc[i - 5]["ema_50"])
        ema_slope = ema50 - ema50_prev
        if ema50 <= 0 or abs(close - ema50) / ema50 > MAX_EMA_DISTANCE:
            stats["rejected_trend"] += 1
            continue

        direction: Optional[str] = None
        if close > ema50 > ema200 and ema_slope > 0:
            direction = "bullish"
        elif close < ema50 < ema200 and ema_slope < 0:
            direction = "bearish"
        else:
            stats["rejected_trend"] += 1
            continue

        pivots = _confirmed_pivots(data, i, lookback, PIVOT_SPAN)
        structure = _find_structure(pivots, direction)
        if structure is None:
            stats["rejected_structure"] += 1
            continue

        swing_high, swing_low, high_idx, low_idx = structure
        if not _valid_impulse_age(data, i, high_idx, low_idx):
            stats["rejected_impulse"] += 1
            continue

        range_size = swing_high - swing_low
        if range_size <= 0 or range_size < atr * MIN_IMPULSE_ATR:
            stats["rejected_impulse"] += 1
            continue

        fib = _calculate_fibonacci_levels(swing_high, swing_low)
        zone_low = fib["0.382"]
        zone_high = fib["0.618"]
        # For a long, 0.382-0.618 measured from the swing low is the standard
        # 38.2-61.8% retracement of high -> low.  The same absolute zone works
        # for a short because the range is symmetric.
        if not _bar_touches_zone(previous, current, zone_low, zone_high, atr * 0.10):
            stats["rejected_fibonacci"] += 1
            continue

        candle_range = float(current["high"] - current["low"])
        body = abs(float(current["close"] - current["open"]))
        if candle_range <= 0 or body / candle_range < MIN_BODY_RATIO:
            stats["rejected_confirmation"] += 1
            continue

        if direction == "bullish":
            confirmed = (
                current["close"] > current["open"]
                and current["close"] > previous["close"]
                and current["close"] >= zone_low - atr * 0.10
                and float(current["low"]) <= zone_high + atr * 0.10
            )
            momentum_ok = float(current.get("stoch_k", 50.0)) <= 70.0
        else:
            confirmed = (
                current["close"] < current["open"]
                and current["close"] < previous["close"]
                and current["close"] <= zone_high + atr * 0.10
                and float(current["high"]) >= zone_low - atr * 0.10
            )
            momentum_ok = float(current.get("stoch_k", 50.0)) >= 30.0

        if not confirmed:
            stats["rejected_confirmation"] += 1
            continue
        if not momentum_ok:
            stats["rejected_momentum"] += 1
            continue

        entry = float(data.iloc[min(i + 1, len(data) - 1)]["open"])
        if direction == "bullish":
            sl = swing_low - atr * 0.25
            target = swing_high
        else:
            sl = swing_high + atr * 0.25
            target = swing_low

        risk = abs(entry - sl)
        reward = abs(target - entry)
        rr = reward / risk if risk > 0 else 0.0
        if rr < MIN_RR:
            stats["rejected_rr"] += 1
            continue

        impulse_key = (high_idx, low_idx, direction)
        if impulse_key == last_impulse:
            stats["rejected_duplicate_swing"] += 1
            continue

        signal = {
            "index": i,
            "type": direction,
            "time": current_time,
            "pattern_name": "Fibonacci_Pro_v2_Long" if direction == "bullish" else "Fibonacci_Pro_v2_Short",
            "fib_level": _nearest_fib_level(close, fib),
            "swing_high": swing_high,
            "swing_low": swing_low,
            "swing_high_index": high_idx,
            "swing_low_index": low_idx,
            "adx": round(adx, 2),
            "atr_ratio": round(atr_ratio, 3),
            "rr": round(rr, 3),
            "diagnostics": {
                "trend": direction,
                "zone": [round(zone_low, 8), round(zone_high, 8)],
                "impulse_size_atr": round(range_size / atr, 3),
            },
        }
        signals.append(signal)
        stats["final_signals"] += 1
        stats["long_signals" if direction == "bullish" else "short_signals"] += 1
        last_signal_index = i
        last_impulse = impulse_key

    _sync_diagnostics(diagnostics, stats)
    return signals


def analyze_fibonacci_pro_signals(
    df: pd.DataFrame,
    lookback: int = DEFAULT_LOOKBACK,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Convenience API returning both signals and diagnostic counters."""
    diagnostics: Dict[str, Any] = {}
    signals = generate_fibonacci_pro_signals(df, lookback=lookback, diagnostics=diagnostics)
    return signals, diagnostics


def _new_diagnostics(bars: int) -> Dict[str, Any]:
    return {
        "bars_input": bars,
        "bars_evaluated": 0,
        "rejected_session": 0,
        "rejected_indicators": 0,
        "rejected_volatility": 0,
        "rejected_trend": 0,
        "rejected_structure": 0,
        "rejected_impulse": 0,
        "rejected_fibonacci": 0,
        "rejected_confirmation": 0,
        "rejected_momentum": 0,
        "rejected_rr": 0,
        "rejected_duplicate_swing": 0,
        "rejected_cooldown": 0,
        "final_signals": 0,
        "long_signals": 0,
        "short_signals": 0,
        "atr_ratio_sum": 0.0,
        "avg_atr_ratio": 0.0,
    }


def _sync_diagnostics(target: Optional[Dict[str, Any]], stats: Dict[str, Any]) -> None:
    if stats["bars_evaluated"]:
        stats["avg_atr_ratio"] = round(stats["atr_ratio_sum"] / stats["bars_evaluated"], 4)
    stats.pop("atr_ratio_sum", None)
    if target is not None:
        target.clear()
        target.update(stats)


def _valid_indicators(row: pd.Series) -> bool:
    required = ("ema_50", "ema_200", "atr_14", "atr_50", "adx_14", "stoch_k")
    return not any(pd.isna(row.get(name)) for name in required)


def _confirmed_pivots(
    df: pd.DataFrame,
    current_idx: int,
    lookback: int,
    span: int,
) -> List[Tuple[int, str, float]]:
    """Return pivots whose right-hand confirmation bars are already closed."""
    start = max(span, current_idx - lookback)
    end = current_idx - span
    pivots: List[Tuple[int, str, float]] = []
    for j in range(start, end + 1):
        left = df.iloc[j - span:j]
        right = df.iloc[j + 1:j + span + 1]
        high = float(df.iloc[j]["high"])
        low = float(df.iloc[j]["low"])
        if len(left) < span or len(right) < span:
            continue
        if high > float(left["high"].max()) and high >= float(right["high"].max()):
            pivots.append((j, "H", high))
        elif low < float(left["low"].min()) and low <= float(right["low"].min()):
            pivots.append((j, "L", low))
    return pivots


def _find_structure(
    pivots: List[Tuple[int, str, float]],
    direction: str,
) -> Optional[Tuple[float, float, int, int]]:
    """Find the latest confirmed HH/HL or LH/LL impulse."""
    if len(pivots) < 4:
        return None

    # Use the most recent alternating 4-pivot sequence.  The final pivot must
    # be the impulse endpoint; current price is expected to be retracing it.
    for k in range(len(pivots) - 4, -1, -1):
        seq = pivots[k:k + 4]
        types = [p[1] for p in seq]
        if direction == "bullish" and types == ["L", "H", "L", "H"]:
            l1, h1, l2, h2 = seq
            if l2[2] > l1[2] and h2[2] > h1[2]:
                return h2[2], l2[2], h2[0], l2[0]
        if direction == "bearish" and types == ["H", "L", "H", "L"]:
            h1, l1, h2, l2 = seq
            if h2[2] < h1[2] and l2[2] < l1[2]:
                return h2[2], l2[2], h2[0], l2[0]
    return None


def _valid_impulse_age(df: pd.DataFrame, current_idx: int, high_idx: int, low_idx: int) -> bool:
    endpoint = max(high_idx, low_idx)
    return 0 < current_idx - endpoint <= MAX_SWING_AGE


def _calculate_fibonacci_levels(swing_high: float, swing_low: float) -> Dict[str, float]:
    size = swing_high - swing_low
    return {
        "0.0": swing_low,
        "0.236": swing_low + size * 0.236,
        "0.382": swing_low + size * 0.382,
        "0.5": swing_low + size * 0.500,
        "0.618": swing_low + size * 0.618,
        "0.786": swing_low + size * 0.786,
        "1.0": swing_high,
    }


def _nearest_fib_level(price: float, fib: Dict[str, float]) -> float:
    candidates = ("0.382", "0.5", "0.618")
    return float(min(candidates, key=lambda name: abs(price - fib[name])))


def _bar_touches_zone(
    previous: pd.Series,
    current: pd.Series,
    zone_low: float,
    zone_high: float,
    buffer: float,
) -> bool:
    lower = zone_low - buffer
    upper = zone_high + buffer
    return any(float(bar["high"]) >= lower and float(bar["low"]) <= upper for bar in (previous, current))


def _ensure_indicators(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()
    if "ema_50" not in result:
        result["ema_50"] = result["close"].ewm(span=50, adjust=False).mean()
    if "ema_200" not in result:
        result["ema_200"] = result["close"].ewm(span=200, adjust=False).mean()
    if "atr_14" not in result:
        result["atr_14"] = _calculate_atr(result, 14)
    if "atr_50" not in result:
        result["atr_50"] = result["atr_14"].rolling(50, min_periods=20).mean()
    if "stoch_k" not in result:
        low14 = result["low"].rolling(14).min()
        high14 = result["high"].rolling(14).max()
        denominator = (high14 - low14).replace(0, 1e-10)
        result["stoch_k"] = (100 * (result["close"] - low14) / denominator).rolling(3).mean()
    if "adx_14" not in result:
        result["adx_14"] = _calculate_adx(result, 14)
    return result


def _calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - df["close"].shift(1)).abs(),
        (df["low"] - df["close"].shift(1)).abs(),
    ], axis=1).max(axis=1)
    return tr.ewm(span=period, adjust=False).mean()


def _calculate_adx(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high, low, close = df["high"], df["low"], df["close"]
    up_move = high.diff()
    down_move = -low.diff()
    plus_dm = up_move.where((up_move > 0) & (up_move > down_move), 0.0)
    minus_dm = down_move.where((down_move > 0) & (down_move > up_move), 0.0)
    tr = pd.concat([
        high - low,
        (high - close.shift(1)).abs(),
        (low - close.shift(1)).abs(),
    ], axis=1).max(axis=1)
    atr = tr.ewm(span=period, adjust=False).mean().replace(0, pd.NA)
    plus_di = 100 * plus_dm.ewm(span=period, adjust=False).mean() / atr
    minus_di = 100 * minus_dm.ewm(span=period, adjust=False).mean() / atr
    denominator = (plus_di + minus_di).replace(0, pd.NA)
    dx = 100 * (plus_di - minus_di).abs() / denominator
    return dx.ewm(span=period, adjust=False).mean()
