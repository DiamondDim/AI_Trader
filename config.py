"""Central project configuration.

MT5 credentials are loaded in this order:
1. environment variables;
2. optional local ``mt5_credentials.py`` (ignored by Git);
3. interactive input when the connector explicitly requests credentials.
"""

import os
from getpass import getpass
from pathlib import Path
from typing import Optional, Tuple

try:
    import mt5_credentials as _local_credentials
except ImportError:
    _local_credentials = None


def _credential(name: str) -> str:
    value = os.getenv(name, "").strip()
    if value:
        return value
    if _local_credentials is not None:
        return str(getattr(_local_credentials, name, "") or "").strip()
    return ""


# --- SECURITY ---
DEMO_MODE = os.getenv("AI_TRADER_DEMO_MODE", "true").lower() in {"1", "true", "yes", "on"}

# --- MT5 ---
MT5_LOGIN_RAW = _credential("MT5_LOGIN")
MT5_PASSWORD = _credential("MT5_PASSWORD")
MT5_SERVER = _credential("MT5_SERVER")
try:
    MT5_LOGIN: Optional[int] = int(MT5_LOGIN_RAW) if MT5_LOGIN_RAW else None
except ValueError:
    MT5_LOGIN = None
MT5_TIMEOUT = int(os.getenv("MT5_TIMEOUT", "60000"))


def get_mt5_credentials(interactive: bool = True) -> Tuple[Optional[int], str, str]:
    """Return MT5 credentials, optionally asking for missing values once.

    No credential is logged. In non-interactive environments missing values
    result in a clean connection failure rather than an exception or hang.
    """
    global MT5_LOGIN, MT5_PASSWORD, MT5_SERVER
    login = MT5_LOGIN
    password = MT5_PASSWORD
    server = MT5_SERVER

    if interactive and (login is None or not password or not server):
        if not getattr(__import__("sys"), "stdin").isatty():
            return login, password, server
        if login is None:
            while login is None:
                raw = input("MT5 login: ").strip()
                try:
                    login = int(raw)
                except ValueError:
                    print("Некорректный MT5 login. Введите число.")
        if not password:
            password = getpass("MT5 password: ")
        if not server:
            server = input("MT5 server: ").strip()
        MT5_LOGIN, MT5_PASSWORD, MT5_SERVER = login, password, server

    return login, password, server


# --- TRADING ---
SYMBOL = os.getenv("AI_TRADER_SYMBOL", "EURUSDrfd")
TIMEFRAME = os.getenv("AI_TRADER_TIMEFRAME", "H1")
RISK_PER_TRADE = float(os.getenv("AI_TRADER_RISK_PER_TRADE", "0.015"))

# --- PATHS ---
BASE_DIR = Path(__file__).parent
LOGS_DIR = BASE_DIR / "logs"
DATA_DIR = BASE_DIR / "data"
LOGS_DIR.mkdir(exist_ok=True)
DATA_DIR.mkdir(exist_ok=True)
