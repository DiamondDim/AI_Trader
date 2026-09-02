"""Interactive MT5 runner for Fibonacci Pro v2.

This runner is deliberately separate from run_fibonacci_pro_test.py so the
existing benchmark remains unchanged.  In addition to Backtester statistics,
it prints the strategy's rejection funnel for every symbol/timeframe.
"""

import os
import sys
from typing import List

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from broker.mt5_connector import get_mt5_connector
from core.backtesting import Backtester
from core.indicators import Indicators
from list_symbols import display_symbols, get_available_symbols, select_symbols
from strategy_intraday.fibonacci_pro_v2 import analyze_fibonacci_pro_signals

TIMEFRAMES = ["M5", "M15", "M30", "H1"]


def _load_data(connector, symbol: str, timeframe: str, bars: int):
    df = connector.get_rates(symbol, timeframe, bars)
    if df.empty:
        return df
    return Indicators().add_all(df, include_ema_200=True)


def _print_diagnostics(stats: dict) -> None:
    print("  Signal funnel:")
    print(f"    bars evaluated:       {stats['bars_evaluated']}")
    print(f"    session rejected:     {stats['rejected_session']}")
    print(f"    indicator rejected:   {stats['rejected_indicators']}")
    print(f"    volatility rejected:  {stats['rejected_volatility']}")
    print(f"    trend rejected:       {stats['rejected_trend']}")
    print(f"    structure rejected:   {stats['rejected_structure']}")
    print(f"    impulse rejected:     {stats['rejected_impulse']}")
    print(f"    fibonacci rejected:   {stats['rejected_fibonacci']}")
    print(f"    confirmation rejected:{stats['rejected_confirmation']}")
    print(f"    momentum rejected:    {stats['rejected_momentum']}")
    print(f"    RR rejected:          {stats['rejected_rr']}")
    print(f"    duplicate swing:      {stats['rejected_duplicate_swing']}")
    print(f"    cooldown rejected:    {stats['rejected_cooldown']}")
    print(f"    FINAL:                 {stats['final_signals']} (L={stats['long_signals']}, S={stats['short_signals']})")
    print(f"    avg ATR ratio:        {stats['avg_atr_ratio']}")


def run_one(connector, symbol: str, timeframe: str, bars: int, balance: float, risk: float):
    print(f"\n{'=' * 76}")
    print(f"{symbol} | {timeframe}")
    print(f"{'=' * 76}")
    df = _load_data(connector, symbol, timeframe, bars)
    if df.empty:
        print("  [!] No market data")
        return None

    signals, diagnostics = analyze_fibonacci_pro_signals(df)
    _print_diagnostics(diagnostics)

    backtester = Backtester(
        initial_balance=balance,
        risk_per_trade=risk,
        atr_sl_multiplier=1.5,
        atr_tp_multiplier=3.0
    )
    result = backtester.run(df, connector, signals, symbol)
    if result:
        print(
            f"  Backtest: trades={result['total_trades']}, "
            f"WR={result['win_rate']}, PF={result['profit_factor']}, "
            f"PnL={result['total_pnl_rub']:.2f} RUB, "
            f"DD={result['max_drawdown_percent']}"
        )
    return result


def main():
    connector = get_mt5_connector()
    if not connector.connect():
        print("[!] MT5 connection failed")
        return

    try:
        symbols = get_available_symbols()
        if not symbols:
            print("[!] No symbols available")
            return
        display_symbols(symbols)
        selected = select_symbols(symbols)
        if not selected:
            print("[!] No symbols selected")
            return

        tf_input = input("Timeframes (M5,M15,M30,H1; default all): ").strip()
        timeframes: List[str] = [x.strip().upper() for x in tf_input.split(",") if x.strip()] if tf_input else TIMEFRAMES
        timeframes = [x for x in timeframes if x in TIMEFRAMES]
        if not timeframes:
            timeframes = TIMEFRAMES

        bars_input = input("Bars (default 5000): ").strip()
        bars = int(bars_input) if bars_input else 5000
        balance_input = input("Initial balance RUB (default 100000): ").strip()
        balance = float(balance_input) if balance_input else 100000.0
        risk_input = input("Risk % (default 1.5): ").strip()
        risk = float(risk_input) / 100.0 if risk_input else 0.015

        selected_symbols = [symbols[idx - 1]['name'] for idx in selected]
        all_results = {}
        for symbol in selected_symbols:
            for timeframe in timeframes:
                result = run_one(connector, symbol, timeframe, bars, balance, risk)
                if result:
                    all_results[(symbol, timeframe)] = result

        print(f"\n{'=' * 76}")
        print("FIBONACCI PRO v2 SUMMARY")
        print(f"{'=' * 76}")
        for (symbol, timeframe), result in all_results.items():
            print(
                f"{symbol:<14} {timeframe:<4} "
                f"trades={result['total_trades']:<4} "
                f"WR={result['win_rate']:<7} "
                f"PF={result['profit_factor']:<6} "
                f"PnL={result['total_pnl_rub']:>12.2f}"
            )
    finally:
        connector.disconnect()


if __name__ == "__main__":
    main()
