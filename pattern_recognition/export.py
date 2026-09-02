import json
from pathlib import Path
from typing import Iterable, Union

from .models import PatternDetection


def export_detections(detections: Iterable[PatternDetection], path: Union[str, Path]) -> Path:
    """Export detections for the MT5 chart bridge or external tooling."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = [d.to_dict() for d in detections]
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return target
