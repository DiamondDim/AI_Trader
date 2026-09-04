from typing import List
import pandas as pd

from .models import PatternDetection, PatternPoint, PatternLevel
from .swings import confirmed_swings


def detect_continuation(df: pd.DataFrame, span: int = 3, lookback: int = 80) -> List[PatternDetection]:
    """Detect conservative flags/pennants/rectangles using confirmed pivots."""
    if len(df) < 12:
        return []
    out = []
    pivots = confirmed_swings(df, span)
    pivots = [x for x in pivots if x[0] >= max(0, len(df)-lookback)]
    for i in range(1, len(pivots)-2):
        a,b,c,d = pivots[i-1:i+3]
        width = max(c[0]-a[0], 1)
        if width > lookback:
            continue
        prices = df.close.iloc[a[0]:d[0]+1].astype(float)
        if prices.empty:
            continue
        atr_proxy = float((df.high-df.low).rolling(14).mean().iloc[d[0]]) if d[0] >= 14 else 0.0
        if atr_proxy <= 0:
            continue
        impulse = abs(b[2]-a[2])
        consolidation = float(prices.max()-prices.min())
        if impulse >= 2.0*atr_proxy and consolidation <= impulse*0.55:
            direction = "bullish" if b[1] == "H" else "bearish"
            name = "Bullish Flag/Pennant" if direction == "bullish" else "Bearish Flag/Pennant"
            out.append(PatternDetection(name, "continuation", direction, 0.74,
                [PatternPoint("A",a[0],df.index[a[0]],a[2]),PatternPoint("B",b[0],df.index[b[0]],b[2]),PatternPoint("C",c[0],df.index[c[0]],c[2]),PatternPoint("D",d[0],df.index[d[0]],d[2])],
                [PatternLevel("range_high", float(prices.max())), PatternLevel("range_low", float(prices.min()))], a[0], d[0]))
    return out
