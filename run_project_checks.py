"""Fast local checks that do not require an MT5 connection or credentials."""

import importlib
import py_compile
from pathlib import Path

import pandas as pd

from core.backtesting import Backtester
from utils.helpers import is_active_session

ROOT = Path(__file__).resolve().parent
IMPORTS = [
    "config", "broker.mt5_connector", "core.backtesting", "core.risk", "core.data_provider",
    "core.indicators", "strategy_intraday.ema_pullback", "strategy_intraday.fibonacci_pro",
    "strategy_intraday.fibonacci_pro_v2", "strategy_swing", "pattern_recognition.detector",
    "pattern_recognition.mt5_commands", "run_pattern_scan", "live_demo_runner",
]


class FakeConnector:
    def get_symbol_info(self, symbol):
        return {"name": symbol, "point": 0.01, "trade_tick_size": 0.01,
                "trade_tick_value": 10.0, "trade_contract_size": 100,
                "volume_min": 0.01, "volume_max": 100.0, "volume_step": 0.01, "spread": 0}


def functional_checks() -> None:
    assert is_active_session(pd.Timestamp("2026-09-07 08:00").to_pydatetime())
    assert not is_active_session(pd.Timestamp("2026-09-05 08:00").to_pydatetime())

    # Timeout exits must remain neutral even when their PnL is positive.
    df = pd.DataFrame({
        "open": [100.0, 100.0, 101.0], "high": [100.5, 100.5, 101.5],
        "low": [99.5, 99.5, 100.5], "close": [100.0, 100.0, 101.2],
        "atr_14": [1.0, 1.0, 1.0],
    })
    result = Backtester(initial_balance=10000, risk_per_trade=0.01).run(
        df, FakeConnector(), [{"index": 0, "type": "bullish", "time": df.index[0]}], "EURUSD"
    )
    assert result["total_trades"] == 1
    assert result["neutrals"] == 1
    assert result["wins"] == 0


def main() -> int:
    print("🔎 AI Trader project checks")
    failures = []
    for path in ROOT.rglob("*.py"):
        if any(part in {".venv", "venv", "env", "__pycache__", ".git"} for part in path.parts):
            continue
        try:
            py_compile.compile(str(path), doraise=True)
        except Exception as exc:
            failures.append(f"compile {path.relative_to(ROOT)}: {exc}")
    for name in IMPORTS:
        try:
            importlib.import_module(name)
        except Exception as exc:
            failures.append(f"import {name}: {exc}")
    if not failures:
        try:
            functional_checks()
        except Exception as exc:
            failures.append(f"functional checks: {exc}")
    if failures:
        print("❌ Checks failed:")
        for item in failures: print(f"  - {item}")
        return 1
    print("✅ Syntax check passed for Python sources")
    print(f"✅ Import check passed for {len(IMPORTS)} project modules")
    print("✅ Calendar and Backtester functional checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
