"""Interactive runner for Fibonacci Pro v2 with cache-first market data."""
from __future__ import annotations

import os
import sys
from typing import List

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from broker.mt5_connector import get_mt5_connector
from core.backtesting import Backtester
from core.data_provider import MarketDataProvider
from core.indicators import Indicators
from list_symbols import display_symbols, get_available_symbols, select_symbols
from strategy_intraday.fibonacci_pro_v2 import analyze_fibonacci_pro_signals

TIMEFRAMES = ["M5", "M15", "M30", "H1"]


def _load_data(provider, symbol: str, timeframe: str, bars: int):
    df = provider.get_rates(symbol, timeframe, bars)
    if df.empty:
        return df
    return Indicators().add_all(df, include_ema_200=True)


def _print_diagnostics(stats: dict) -> None:
    print("  Signal funnel:")
    for key, label in (("bars_evaluated", "bars evaluated"), ("rejected_session", "session rejected"),
                       ("rejected_indicators", "indicator rejected"), ("rejected_volatility", "volatility rejected"),
                       ("rejected_trend", "trend rejected"), ("rejected_structure", "structure rejected"),
                       ("rejected_impulse", "impulse rejected"), ("rejected_fibonacci", "fibonacci rejected"),
                       ("rejected_confirmation", "confirmation rejected"), ("rejected_momentum", "momentum rejected"),
                       ("rejected_rr", "RR rejected"), ("rejected_duplicate_swing", "duplicate swing"),
                       ("rejected_cooldown", "cooldown rejected")):
        print(f"    {label:<22} {stats[key]}")
    print(f"    {'FINAL':<22} {stats['final_signals']} (L={stats['long_signals']}, S={stats['short_signals']})")
    print(f"    {'avg ATR ratio':<22} {stats['avg_atr_ratio']}")


def run_one(provider, connector, symbol: str, timeframe: str, bars: int, balance: float, risk: float):
    print(f"\n{'=' * 76}\n{symbol} | {timeframe}\n{'=' * 76}")
    df = _load_data(provider, symbol, timeframe, bars)
    if df.empty:
        print("  [!] No market data"); return None
    signals, diagnostics = analyze_fibonacci_pro_signals(df)
    _print_diagnostics(diagnostics)
    result = Backtester(initial_balance=balance, risk_per_trade=risk,
                        atr_sl_multiplier=1.5, atr_tp_multiplier=3.0).run(df, connector, signals, symbol)
    if result:
        print(f"  Backtest: trades={result['total_trades']}, WR={result['win_rate']}, PF={result['profit_factor']}, PnL={result['total_pnl_rub']:.2f} RUB, DD={result['max_drawdown_percent']}")
    return result


def main():
    connector = get_mt5_connector()
    if not connector.connect():
        print("[!] MT5 connection failed"); return
    try:
        provider = MarketDataProvider(connector)
        symbols = get_available_symbols()
        if not symbols: print("[!] No symbols available"); return
        display_symbols(symbols)
        selected = select_symbols(symbols)
        if not selected: print("[!] No symbols selected"); return
        tf_input = input("Timeframes (M5,M15,M30,H1; default all): ").strip()
        timeframes: List[str] = [x.strip().upper() for x in tf_input.split(",") if x.strip()] if tf_input else TIMEFRAMES
        timeframes = [x for x in timeframes if x in TIMEFRAMES] or TIMEFRAMES
        bars_input = input("Bars (default 5000): ").strip(); bars = int(bars_input) if bars_input else 5000
        balance_input = input("Initial balance RUB (default 100000): ").strip(); balance = float(balance_input) if balance_input else 100000.0
        risk_input = input("Risk % (default 1.5): ").strip(); risk = float(risk_input) / 100.0 if risk_input else 0.015
        all_results = {}
        for idx in selected:
            symbol = symbols[idx - 1]['name']
            for timeframe in timeframes:
                result = run_one(provider, connector, symbol, timeframe, bars, balance, risk)
                if result: all_results[(symbol, timeframe)] = result
        print(f"\n{'=' * 76}\nFIBONACCI PRO v2 SUMMARY\n{'=' * 76}")
        for (symbol, timeframe), result in all_results.items():
            print(f"{symbol:<14} {timeframe:<4} trades={result['total_trades']:<4} WR={result['win_rate']:<7} PF={result['profit_factor']:<6} PnL={result['total_pnl_rub']:>12.2f}")
    finally:
        connector.disconnect()


if __name__ == "__main__":
    main()
