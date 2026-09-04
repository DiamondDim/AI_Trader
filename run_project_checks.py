"""Fast local checks that do not require an MT5 connection or credentials."""

import importlib
import py_compile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
IMPORTS = [
    "config", "broker.mt5_connector", "core.backtesting", "core.risk",
    "core.data_provider", "core.indicators", "strategy_intraday.ema_pullback",
    "strategy_intraday.fibonacci_pro", "strategy_intraday.fibonacci_pro_v2",
    "strategy_swing", "pattern_recognition.detector", "pattern_recognition.mt5_commands",
    "run_pattern_scan", "live_demo_runner",
]


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
    if failures:
        print("❌ Checks failed:")
        for item in failures: print(f"  - {item}")
        return 1
    print("✅ Syntax check passed for Python sources")
    print(f"✅ Import check passed for {len(IMPORTS)} project modules")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
