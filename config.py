import os
from pathlib import Path

# --- НАСТРОЙКИ БЕЗОПАСНОСТИ ---
DEMO_MODE = os.getenv("AI_TRADER_DEMO_MODE", "true").lower() in {"1", "true", "yes", "on"}

# --- НАСТРОЙКИ MT5 ---
# Credentials are read from environment variables. Do not commit them to Git.
MT5_LOGIN = int(os.getenv("MT5_LOGIN", "0"))
MT5_PASSWORD = os.getenv("MT5_PASSWORD", "")
MT5_SERVER = os.getenv("MT5_SERVER", "")
MT5_TIMEOUT = int(os.getenv("MT5_TIMEOUT", "60000"))

# --- НАСТРОЙКИ ТОРГОВЛИ ---
SYMBOL = os.getenv("AI_TRADER_SYMBOL", "EURUSDrfd")
TIMEFRAME = os.getenv("AI_TRADER_TIMEFRAME", "H1")
# Preserve the latest source-branch default (1.5%) while allowing environment override.
RISK_PER_TRADE = float(os.getenv("AI_TRADER_RISK_PER_TRADE", "0.015"))

# --- ПУТИ ---
BASE_DIR = Path(__file__).parent
LOGS_DIR = BASE_DIR / "logs"
DATA_DIR = BASE_DIR / "data"
LOGS_DIR.mkdir(exist_ok=True)
DATA_DIR.mkdir(exist_ok=True)
