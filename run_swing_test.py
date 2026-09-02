"""Interactive Swing strategy runner using the shared backtester and cache."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from broker.mt5_connector import get_mt5_connector
from core.backtesting import Backtester
from core.data_provider import MarketDataProvider
from core.indicators import Indicators
from list_symbols import display_symbols, get_available_symbols, select_symbols
from strategy_swing.swing import analyze_swing_signals


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
        bars_input = input("Bars H1 (default 5000): ").strip(); bars = int(bars_input) if bars_input else 5000
        balance_input = input("Initial balance RUB (default 100000): ").strip(); balance = float(balance_input) if balance_input else 100000.0
        risk_input = input("Risk % (default 1.0): ").strip(); risk = float(risk_input) / 100.0 if risk_input else 0.01
        for idx in selected:
            symbol = symbols[idx - 1]['name']
            print(f"\n{'=' * 76}\nSWING | {symbol} | H1\n{'=' * 76}")
            df = provider.get_rates(symbol, "H1", bars)
            if df.empty:
                print("[!] No market data"); continue
            df = Indicators().add_all(df, include_ema_200=True)
            signals, diagnostics = analyze_swing_signals(df)
            print(f"Signals: raw={diagnostics['raw_signals']}, final={diagnostics['final_signals']}, ADX rejected={diagnostics['rejected_adx']}, Stoch rejected={diagnostics['rejected_stochastic']}, session rejected={diagnostics['rejected_session']}")
            result = Backtester(initial_balance=balance, risk_per_trade=risk, atr_sl_multiplier=1.5, atr_tp_multiplier=3.0).run(df, connector, signals, symbol)
            if result:
                print(f"Result: trades={result['total_trades']}, WR={result['win_rate']}, PF={result['profit_factor']}, PnL={result['total_pnl_rub']:.2f} RUB, DD={result['max_drawdown_percent']}")
    finally:
        connector.disconnect()


if __name__ == "__main__":
    main()
