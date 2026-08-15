# core/patterns/candlestick.py
from .base import BasePattern
import pandas as pd
from typing import List, Dict, Any


class BullishEngulfing(BasePattern):
    """
    Паттерн "Бычье поглощение".
    Состоит из двух свечей: первая медвежья, вторая бычья,
    и тело второй свечи полностью перекрывает тело первой.
    """

    def __init__(self):
        super().__init__(name="Bullish Engulfing", category="candlestick")

    def detect(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        detections = []

        # Для паттерна нужно как минимум 2 свечи
        if len(df) < 2:
            return detections

        # Проходим по данным, начиная со второй свечи
        for i in range(1, len(df)):
            prev = df.iloc[i - 1]  # Первая свеча (медвежья)
            curr = df.iloc[i]  # Вторая свеча (бычья)

            # Условия паттерна
            is_bearish = prev['close'] < prev['open']
            is_bullish = curr['close'] > curr['open']

            # Вторая свеча должна полностью поглощать тело первой
            engulfs = (curr['open'] <= prev['close']) and (curr['close'] >= prev['open'])

            if is_bearish and is_bullish and engulfs:
                detections.append({
                    'index': i,
                    'time': df.index[i],
                    'type': 'bullish',
                    'confidence': 1.0,
                    'open': curr['open'],
                    'close': curr['close']
                })

        return detections


class BearishEngulfing(BasePattern):
    """
    Паттерн "Медвежье поглощение".
    Первая свеча бычья, вторая медвежья, тело второй полностью перекрывает тело первой.
    Сигнал на продажу.
    """

    def __init__(self):
        super().__init__(name="Bearish Engulfing", category="candlestick")

    def detect(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        detections = []
        if len(df) < 2:
            return detections

        for i in range(1, len(df)):
            prev = df.iloc[i - 1]
            curr = df.iloc[i]

            is_bullish = prev['close'] > prev['open']
            is_bearish = curr['close'] < curr['open']
            engulfs = (curr['open'] >= prev['close']) and (curr['close'] <= prev['open'])

            if is_bullish and is_bearish and engulfs:
                detections.append({
                    'index': i,
                    'time': df.index[i],
                    'type': 'bearish',
                    'confidence': 1.0,
                    'open': curr['open'],
                    'close': curr['close']
                })
        return detections


class Doji(BasePattern):
    """
    Паттерн "Доджи".
    Свеча с очень маленьким телом и длинными тенями. Сигнал неопределенности и возможного разворота.
    """

    def __init__(self):
        super().__init__(name="Doji", category="candlestick")

    def detect(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        detections = []
        if len(df) < 1:
            return detections

        for i in range(len(df)):
            curr = df.iloc[i]
            body = abs(curr['close'] - curr['open'])
            full_range = curr['high'] - curr['low']

            # Тело должно быть меньше 10% от полного диапазона свечи
            if full_range > 0 and (body / full_range) < 0.05:
                detections.append({
                    'index': i,
                    'time': df.index[i],
                    'type': 'neutral',
                    'confidence': 0.7,
                    'open': curr['open'],
                    'close': curr['close']
                })
        return detections


class Hammer(BasePattern):
    """
    Паттерн "Молот".
    Маленькое тело в верхней части свечи и длинная нижняя тень (минимум в 2 раза больше тела).
    Бычий сигнал разворота после нисходящего тренда.
    """

    def __init__(self):
        super().__init__(name="Hammer", category="candlestick")

    def detect(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        detections = []
        if len(df) < 1:
            return detections

        for i in range(len(df)):
            curr = df.iloc[i]
            body = abs(curr['close'] - curr['open'])
            lower_shadow = min(curr['open'], curr['close']) - curr['low']
            upper_shadow = curr['high'] - max(curr['open'], curr['close'])

            # Нижняя тень должна быть минимум в 2 раза больше тела
            # Верхняя тень должна быть маленькой
            if body > 0 and lower_shadow >= (2 * body) and upper_shadow <= body:
                detections.append({
                    'index': i,
                    'time': df.index[i],
                    'type': 'bullish',
                    'confidence': 0.85,
                    'open': curr['open'],
                    'close': curr['close']
                })
        return detections
