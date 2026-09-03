from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass(frozen=True)
class PatternPoint:
    name: str
    index: int
    time: object
    price: float


@dataclass(frozen=True)
class PatternLevel:
    name: str
    price: float


@dataclass
class PatternDetection:
    name: str
    category: str
    direction: str
    confidence: float
    points: List[PatternPoint] = field(default_factory=list)
    levels: List[PatternLevel] = field(default_factory=list)
    start_index: int = 0
    end_index: int = 0
    status: str = "confirmed"
    metadata: Dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, object]:
        # Безопасная обработка уровней: проверяем, является ли levels списком
        levels_dict = {}
        if isinstance(self.levels, list):
            try:
                levels_dict = {level.name: level.price for level in self.levels if hasattr(level, 'name')}
            except Exception:
                levels_dict = {"error": "invalid_level_format"}

        return {
            "pattern": self.name,
            "category": self.category,
            "direction": self.direction,
            "confidence": round(float(self.confidence), 4),
            "points": {
                p.name: {"index": p.index, "time": str(p.time), "price": p.price}
                for p in self.points if hasattr(p, 'name')
            },
            "levels": levels_dict,
            "start_index": self.start_index,
            "end_index": self.end_index,
            "status": self.status,
            "metadata": self.metadata,
        }
