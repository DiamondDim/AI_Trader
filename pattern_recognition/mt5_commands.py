from pathlib import Path
from typing import Iterable, Union

from .models import PatternDetection


def export_mt5_commands(detections: Iterable[PatternDetection], path: Union[str, Path]) -> Path:
    """Write deterministic commands consumed by pattern_recognition/mt5_bridge.mq5."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    for n, d in enumerate(detections):
        points = d.points
        for a, b in zip(points, points[1:]):
            color = 65280 if d.direction == "bullish" else 255 if d.direction == "bearish" else 65535
            name = f"{d.name}_{d.end_index}_{n}_{a.name}_{b.name}".replace(" ", "_")
            lines.append(f"LINE|{name}|{a.time}|{a.price}|{b.time}|{b.price}|{color}")
    target.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    return target
