from typing import List
import pandas as pd

from .models import PatternDetection, PatternPoint, PatternLevel
from .swings import confirmed_swings


def detect_chart_patterns(df: pd.DataFrame, span: int = 3, tolerance: float = 0.003) -> List[PatternDetection]:
    """Detect conservative double tops/bottoms and head-and-shoulders from confirmed pivots."""
    pivots = confirmed_swings(df, span)
    out: List[PatternDetection] = []
    if len(pivots) < 3:
        return out
    for a, b, c in zip(pivots, pivots[1:], pivots[2:]):
        if a[1] == "H" and b[1] == "L" and c[1] == "H":
            if abs(a[2] - c[2]) / max(abs(a[2]), 1e-12) <= tolerance and b[2] < min(a[2], c[2]):
                out.append(PatternDetection("Double Top", "chart", "bearish", 0.82,
                    [PatternPoint("A",a[0],df.index[a[0]],a[2]),PatternPoint("B",b[0],df.index[b[0]],b[2]),PatternPoint("C",c[0],df.index[c[0]],c[2])],
                    [PatternLevel("neckline", b[2])], a[0], c[0]))
        if a[1] == "L" and b[1] == "H" and c[1] == "L":
            if abs(a[2] - c[2]) / max(abs(a[2]), 1e-12) <= tolerance and b[2] > max(a[2], c[2]):
                out.append(PatternDetection("Double Bottom", "chart", "bullish", 0.82,
                    [PatternPoint("A",a[0],df.index[a[0]],a[2]),PatternPoint("B",b[0],df.index[b[0]],b[2]),PatternPoint("C",c[0],df.index[c[0]],c[2])],
                    [PatternLevel("neckline", b[2])], a[0], c[0]))
    for i in range(len(pivots) - 4):
        a,b,c,d,e = pivots[i:i+5]
        if [x[1] for x in (a,b,c,d,e)] == ["H","L","H","L","H"] and c[2] > a[2] and c[2] > e[2] and abs(a[2]-e[2])/a[2] <= tolerance:
            out.append(PatternDetection("Head and Shoulders", "chart", "bearish", 0.88,
                [PatternPoint(n,p[0],df.index[p[0]],p[2]) for n,p in zip("ABCDE",(a,b,c,d,e))],
                [PatternLevel("neckline", (b[2]+d[2])/2)], a[0], e[0]))
        if [x[1] for x in (a,b,c,d,e)] == ["L","H","L","H","L"] and c[2] < a[2] and c[2] < e[2] and abs(a[2]-e[2])/a[2] <= tolerance:
            out.append(PatternDetection("Inverse Head and Shoulders", "chart", "bullish", 0.88,
                [PatternPoint(n,p[0],df.index[p[0]],p[2]) for n,p in zip("ABCDE",(a,b,c,d,e))],
                [PatternLevel("neckline", (b[2]+d[2])/2)], a[0], e[0]))
    return out
