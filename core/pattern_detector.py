import pandas as pd
from typing import List, Dict, Any
from utils.logger import LoggingMixin
from .patterns.base import BasePattern


class PatternDetector(LoggingMixin):
    """
    Движок распознавания паттернов.
    Управляет списком активных паттернов и сканирует рынок.
    """

    def __init__(self) -> None:
        super().__init__()
        self._patterns: List[BasePattern] = []
        self.log_info("Pattern Detector initialized.")

    def register_pattern(self, pattern: BasePattern):
        """Добавляет новый паттерн в систему."""
        if not isinstance(pattern, BasePattern):
            raise TypeError("Pattern must be an instance of BasePattern")
        self._patterns.append(pattern)
        self.log_info(f"Registered pattern: {pattern.name}")

    def scan(self, df: pd.DataFrame) -> Dict[str, List[Dict[str, Any]]]:
        """
        Сканирует переданный DataFrame на наличие всех зарегистрированных паттернов.

        Args:
            df: DataFrame с данными от MT5 (из mt5_connector.get_rates)

        Returns:
            Словарь вида: {'pattern_name': [найденные совпадения]}
        """
        if df.empty:
            self.log_warning("Received empty DataFrame for scanning.")
            return {}

        results = {}
        self.log_debug(f"Scanning {len(df)} bars with {len(self._patterns)} patterns...")

        for pattern in self._patterns:
            try:
                detections = pattern.detect(df)
                if detections:
                    results[pattern.name] = detections
                    self.log_info(f"Found {len(detections)} '{pattern.name}' patterns.")
            except Exception as e:
                self.log_error(f"Error detecting {pattern.name}: {e}")

        return results
