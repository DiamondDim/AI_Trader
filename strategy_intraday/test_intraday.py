import pandas as pd
from typing import Callable, List, Dict, Any
from broker.mt5_connector import get_mt5_connector
from core.backtesting import Backtester
from core.data_provider import MarketDataProvider
from core.indicators import Indicators

TIMEFRAME_MAP = {'M5': 'M5', 'M15': 'M15', 'M30': 'M30', 'H1': 'H1'}


def _ensure_core_indicators(df: pd.DataFrame, include_ema_200: bool = True) -> pd.DataFrame:
    return Indicators().add_all(df, include_ema_200=include_ema_200)


def run_intraday_backtest(symbol: str, timeframe_str: str, bars: int, initial_balance: float,
                          signal_generator: Callable[[pd.DataFrame], List[Dict[str, Any]]],
                          sl_mult: float = 1.5, tp_mult: float = 3.0, risk_per_trade: float = 0.01):
    if timeframe_str not in TIMEFRAME_MAP:
        raise ValueError(f"Таймфрейм {timeframe_str} не поддерживается.")
    connector = get_mt5_connector()
    if not connector.connect():
        print("[!] Ошибка подключения к MT5. Проверь config.py"); return None
    try:
        print(f"[*] Загрузка {bars} баров для {symbol} ({timeframe_str})...")
        df = MarketDataProvider(connector).get_rates(symbol, timeframe_str, bars)
        if df.empty:
            print("[!] Не удалось получить данные."); return None
        df = _ensure_core_indicators(df, include_ema_200=True)
        print("[*] Генерация сигналов стратегии...")
        signals = signal_generator(df)
        print(f"[*] Найдено {len(signals)} потенциальных сделок.")
        return Backtester(initial_balance=initial_balance, risk_per_trade=risk_per_trade,
                          atr_sl_multiplier=sl_mult, atr_tp_multiplier=tp_mult).run(df, connector, signals, symbol)
    finally:
        connector.disconnect()


def test_multiple_timeframes(symbol: str, timeframes: list[str], bars: int, initial_balance: float,
                             signal_generator: Callable, risk_per_trade: float = 0.01):
    results = {}
    for tf in timeframes:
        print(f"\n{'=' * 60}\nТЕСТ НА ТАЙМФРЕЙМЕ: {tf}\n{'=' * 60}")
        stats = run_intraday_backtest(symbol, tf, bars, initial_balance, signal_generator,
                                      sl_mult=1.0, tp_mult=2.0, risk_per_trade=risk_per_trade)
        if stats: results[tf] = stats
    return results


# Legacy helpers retained for compatibility with external callers.
def _calculate_atr_inline(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    ranges = pd.concat([df['high'] - df['low'], (df['high'] - df['close'].shift()).abs(),
                        (df['low'] - df['close'].shift()).abs()], axis=1)
    df['atr_14'] = ranges.max(axis=1).rolling(window=period).mean(); return df


def _calculate_adx_inline(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    return Indicators().add_adx(df, period=period)


def run_mtf_backtest(symbol: str, main_timeframe: str, older_timeframe: str, bars_main: int, bars_older: int,
                     initial_balance: float, signal_generator: Callable, sl_mult: float = 1.5,
                     tp_mult: float = 3.0, risk_per_trade: float = 0.01):
    connector = get_mt5_connector()
    if not connector.connect(): print("[!] Ошибка подключения к MT5"); return None
    try:
        provider = MarketDataProvider(connector)
        print(f"[*] Загрузка MTF данных для {symbol}: {main_timeframe} + {older_timeframe}")
        df_main = provider.get_rates(symbol, main_timeframe, bars_main)
        df_older = provider.get_rates(symbol, older_timeframe, bars_older)
        if df_main.empty or df_older.empty: print("[!] Не удалось получить данные"); return None
        df_main = _ensure_core_indicators(df_main, True); df_older = _ensure_core_indicators(df_older, True)
        signals = signal_generator(df_main, df_older)
        return Backtester(initial_balance=initial_balance, risk_per_trade=risk_per_trade,
                          atr_sl_multiplier=sl_mult, atr_tp_multiplier=tp_mult).run(df_main, connector, signals, symbol)
    finally:
        connector.disconnect()
