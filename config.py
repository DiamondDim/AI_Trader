import os
from pathlib import Path

# --- НАСТРОЙКИ БЕЗОПАСНОСТИ ---
# ВНИМАНИЕ: Всегда True при разработке и тестировании!
# Бот НЕ будет открывать реальные ордера, если этот флаг True.
DEMO_MODE = True

# --- НАСТРОЙКИ MT5 ---
# Заполни своими данными от демо-счета
MT5_LOGIN = 2000067543  # Твой логин
MT5_PASSWORD = "s8gvkDbd@Z"  # Твой пароль
MT5_SERVER = "AlfaForexRU-Real"  # Название сервера (например, "MetaQuotes-Demo")
MT5_TIMEOUT = 60000  # Таймаут подключения в мс

# --- НАСТРОЙКИ ТОРГОВЛИ ---
SYMBOL = "EURUSDrfd"  # Основной инструмент для теста
TIMEFRAME = "H1"   # Таймфрейм
RISK_PER_TRADE = 0.015  # Риск на сделку (1,5%)

# --- ПУТИ ---
BASE_DIR = Path(__file__).parent
LOGS_DIR = BASE_DIR / "logs"
DATA_DIR = BASE_DIR / "data"

# Создаем папки, если их нет
LOGS_DIR.mkdir(exist_ok=True)
DATA_DIR.mkdir(exist_ok=True)
