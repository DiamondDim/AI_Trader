from abc import ABC, abstractmethod
from typing import List, Dict, Any
import pandas as pd


class BasePattern(ABC):
    """
    Базовый класс для всех торговых паттернов.
    Любой новый паттерн должен наследоваться от него.
    """

    def __init__(self, name: str, category: str):
        self.name = name
        self.category = category  # 'candlestick', 'geometric', 'harmonic'

    @abstractmethod
    def detect(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """
        Метод для поиска паттерна в исторических данных.

        Args:
            df: DataFrame с историческими данными (open, high, low, close, volume)

        Returns:
            Список словарей с найденными паттернами.
            Пример: [{'index': 10, 'type': 'bullish', 'confidence': 0.85}]
        """
        pass

    def __repr__(self):
        return f"<Pattern: {self.name} ({self.category})>"
