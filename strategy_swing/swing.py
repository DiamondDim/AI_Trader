"""Swing strategy reconstructed from the dev_010 strategy specification.

The source branch contains the executable specification in test_swing.py but
not a standalone strategy module. This implementation preserves those rules:
EMA50 trend, ADX>20, stochastic zones, active session, and the four registered
candlestick patterns (BullishEngulfing, BearishEngulfing, Doji, Hammer).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from core.indicators import Indicators
from core.pattern_detector import PatternDetector
from core.patterns.candlestick import BullishEngulfing, BearishEngulfing, Doji, Hammer
from utils.helpers import is_active_session


DEFAULT_ADX = 20.0
BULLISH_STOCH_MAX = 30.0
BEARISH_STOCH_MIN = 70.0


def _detector() -> PatternDetector:
    detector = PatternDetector()
    detector.register_pattern(BullishEngulfing())
    detector.register_pattern(BearishEngulfing())
    detector.register_pattern(Doji())
    detector.register_pattern(Hammer())
    return detector


def generate_swing_signals(df: pd.DataFrame, diagnostics: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    stats = {"bars_input": 0 if df is None else len(df), "raw_signals": 0, "rejected_neutral": 0,
             "rejected_trend": 0, "rejected_adx": 0, "rejected_stochastic": 0,
             "rejected_session": 0, "final_signals": 0}
    if diagnostics is not None:
        diagnostics.clear(); diagnostics.update(stats)
    if df is None or df.empty or not {"open", "high", "low", "close"}.issubset(df.columns):
        return []

    data = df.copy()
    Indicators().add_ema(data, 50)
    Indicators().add_atr(data, 14)
    Indicators().add_stochastic(data, 14, 3, 3)
    Indicators().add_adx(data, 14)

    results = _detector().scan(data)
    signals: List[Dict[str, Any]] = []
    for pattern_name, detections in results.items():
        for det in detections:
            stats["raw_signals"] += 1
            idx = int(det["index"])
            signal_type = det["type"]
            signal_time = det["time"]
            if signal_type == "neutral":
                stats["rejected_neutral"] += 1; continue
            close = float(data["close"].iloc[idx]); ema50 = float(data["ema_50"].iloc[idx])
            if signal_type == "bullish" and close <= ema50 or signal_type == "bearish" and close >= ema50:
                stats["rejected_trend"] += 1; continue
            adx = float(data["adx_14"].iloc[idx]) if not pd.isna(data["adx_14"].iloc[idx]) else 0.0
            if adx < DEFAULT_ADX:
                stats["rejected_adx"] += 1; continue
            stoch = data["stoch_k"].iloc[idx]
            if pd.isna(stoch):
                stats["rejected_stochastic"] += 1; continue
            stoch = float(stoch)
            if signal_type == "bullish" and stoch >= BULLISH_STOCH_MAX or signal_type == "bearish" and stoch <= BEARISH_STOCH_MIN:
                stats["rejected_stochastic"] += 1; continue
            if not is_active_session(signal_time):
                stats["rejected_session"] += 1; continue
            signal = dict(det)
            signal["pattern_name"] = pattern_name
            signal["adx"] = round(adx, 2)
            signal["stoch_k"] = round(stoch, 2)
            signal["ema_50"] = ema50
            signal["atr_14"] = float(data["atr_14"].iloc[idx]) if not pd.isna(data["atr_14"].iloc[idx]) else None
            signals.append(signal)
            stats["final_signals"] += 1
    if diagnostics is not None:
        diagnostics.clear(); diagnostics.update(stats)
    return signals


def analyze_swing_signals(df: pd.DataFrame) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    diagnostics: Dict[str, Any] = {}
    return generate_swing_signals(df, diagnostics=diagnostics), diagnostics
