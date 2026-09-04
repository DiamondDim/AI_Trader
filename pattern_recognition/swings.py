from typing import List, Tuple
import pandas as pd


def confirmed_swings(df: pd.DataFrame, span: int = 3) -> List[Tuple[int, str, float]]:
    """Return pivots only after `span` bars on both sides have closed."""
    if len(df) < 2 * span + 1:
        return []
    highs = df.high.astype(float).to_numpy()
    lows = df.low.astype(float).to_numpy()
    result = []
    for i in range(span, len(df) - span):
        window_h = highs[i-span:i+span+1]
        window_l = lows[i-span:i+span+1]
        if highs[i] == window_h.max() and (window_h == highs[i]).sum() == 1:
            result.append((i, "H", highs[i]))
        if lows[i] == window_l.min() and (window_l == lows[i]).sum() == 1:
            result.append((i, "L", lows[i]))
    return sorted(result, key=lambda x: x[0])
