from typing import List
import pandas as pd

from .models import PatternDetection, PatternPoint
from .swings import confirmed_swings


def _ratio(a, b, c):
    return abs(b-a) / max(abs(c-a), 1e-12)


def detect_harmonic(df: pd.DataFrame, span: int = 3, tolerance: float = 0.08) -> List[PatternDetection]:
    """Detect conservative XABCD Gartley/Bat/Butterfly/Crab candidates.

    Ratios are checked on confirmed pivots only. A candidate is reported after D is
    confirmed, making this suitable for research without future-bar leakage.
    """
    p = confirmed_swings(df, span)
    out = []
    for i in range(len(p) - 4):
        x,a,b,c,d = p[i:i+5]
        if len({x[1],a[1],b[1],c[1],d[1]}) != 2:
            continue
        if not (x[1] != a[1] and a[1] != b[1] and b[1] != c[1] and c[1] != d[1]):
            continue
        xa, ab, bc, cd = abs(a[2]-x[2]), abs(b[2]-a[2]), abs(c[2]-b[2]), abs(d[2]-c[2])
        if min(xa,ab,bc,cd) <= 0:
            continue
        ab_xa, bc_ab, cd_bc = ab/xa, bc/ab, cd/bc
        ad_xa = abs(d[2]-x[2])/xa
        specs = {
            "Gartley": ((0.618,0.618),(0.382,0.886),(1.13,1.618),(0.786,0.786)),
            "Bat": ((0.382,0.50),(0.382,0.886),(1.618,2.618),(0.886,0.886)),
            "Butterfly": ((0.786,0.786),(0.382,0.886),(1.618,2.618),(1.27,1.618)),
            "Crab": ((0.382,0.618),(0.382,0.886),(2.24,3.618),(1.618,1.618)),
        }
        for name, (r1,r2,r3,r4) in specs.items():
            checks = [r1[0] <= ab_xa <= r1[1], r2[0] <= bc_ab <= r2[1], r3[0] <= cd_bc <= r3[1], r4[0]-tolerance <= ad_xa <= r4[1]+tolerance]
            if sum(checks) >= 3:
                direction = "bullish" if d[1] == "L" else "bearish"
                confidence = 0.65 + 0.08 * sum(checks)
                out.append(PatternDetection(name, "harmonic", direction, min(confidence, 0.97),
                    [PatternPoint(n,z[0],df.index[z[0]],z[2]) for n,z in zip("XABCD",(x,a,b,c,d))],
                    start_index=x[0], end_index=d[0], metadata={"AB_XA":ab_xa,"BC_AB":bc_ab,"CD_BC":cd_bc,"AD_XA":ad_xa}))
                break
    return out
