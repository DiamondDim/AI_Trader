from typing import Dict, List, Optional
import pandas as pd

from .models import PatternDetection
from .candlestick import detect_candlesticks
from .chart import detect_chart_patterns
from .harmonic import detect_harmonic
from .continuation import detect_continuation


class PatternRecognitionEngine:
    """Unified, strategy-independent pattern scanner."""

    def __init__(self, swing_span: int = 3, min_confidence: float = 0.70):
        self.swing_span = swing_span
        self.min_confidence = min_confidence

    def scan(self, df: pd.DataFrame, categories: Optional[List[str]] = None) -> List[PatternDetection]:
        categories = set(categories or ["candlestick", "chart", "harmonic", "continuation"])
        detections: List[PatternDetection] = []
        if "candlestick" in categories:
            detections.extend(detect_candlesticks(df))
        if "chart" in categories:
            detections.extend(detect_chart_patterns(df, self.swing_span))
        if "harmonic" in categories:
            detections.extend(detect_harmonic(df, self.swing_span))
        if "continuation" in categories:
            detections.extend(detect_continuation(df, self.swing_span))
        return [d for d in detections if d.confidence >= self.min_confidence]

    def scan_dict(self, df: pd.DataFrame, categories: Optional[List[str]] = None) -> List[Dict]:
        return [d.to_dict() for d in self.scan(df, categories)]
