from typing import List
import pandas as pd

from .models import PatternDetection, PatternPoint


def _point(df, name: str, i: int, price: float) -> PatternPoint:
    return PatternPoint(name, i, df.index[i], float(price))


def detect_candlesticks(df: pd.DataFrame) -> List[PatternDetection]:
    """Detect confirmed single/two/three-candle formations without look-ahead."""
    required = {"open", "high", "low", "close"}
    if len(df) < 2 or not required.issubset(df.columns):
        return []
    out: List[PatternDetection] = []
    for i in range(len(df)):
        c = df.iloc[i]
        o, h, l, cl = map(float, (c.open, c.high, c.low, c.close))
        rng = h - l
        if rng <= 0:
            continue
        body = abs(cl - o)
        upper = h - max(o, cl)
        lower = min(o, cl) - l
        ts = df.index[i]
        p = _point
        if body / rng <= 0.10:
            out.append(PatternDetection("Doji", "candlestick", "neutral", 0.72,
                [p(df, "C", i, cl)], i, i))
        if body > 0 and lower >= 2 * body and upper <= body:
            out.append(PatternDetection("Hammer", "candlestick", "bullish", 0.82,
                [p(df, "C", i, cl)], i, i))
        if body > 0 and upper >= 2 * body and lower <= body:
            out.append(PatternDetection("Shooting Star", "candlestick", "bearish", 0.82,
                [p(df, "C", i, cl)], i, i))
        if i >= 1:
            prev = df.iloc[i - 1]
            po, pc = float(prev.open), float(prev.close)
            if pc < po and cl > o and o <= pc and cl >= po:
                out.append(PatternDetection("Bullish Engulfing", "candlestick", "bullish", 0.90,
                    [p(df, "A", i-1, pc), p(df, "B", i, cl)], i-1, i))
            if pc > po and cl < o and o >= pc and cl <= po:
                out.append(PatternDetection("Bearish Engulfing", "candlestick", "bearish", 0.90,
                    [p(df, "A", i-1, pc), p(df, "B", i, cl)], i-1, i))
        if i >= 2:
            a, b = df.iloc[i-2], df.iloc[i-1]
            ao, ac = float(a.open), float(a.close)
            bo, bc = float(b.open), float(b.close)
            ar = float(a.high - a.low)
            if ac < ao and bc < bo and cl > o and ar > 0 and abs(bc-bo) <= ar * .35 and cl > (ao+ac)/2:
                out.append(PatternDetection("Morning Star", "candlestick", "bullish", 0.78,
                    [p(df,"A",i-2,ac),p(df,"B",i-1,bc),p(df,"C",i,cl)], i-2, i))
            if ac > ao and bc > bo and cl < o and ar > 0 and abs(bc-bo) <= ar * .35 and cl < (ao+ac)/2:
                out.append(PatternDetection("Evening Star", "candlestick", "bearish", 0.78,
                    [p(df,"A",i-2,ac),p(df,"B",i-1,bc),p(df,"C",i,cl)], i-2, i))
    return out
