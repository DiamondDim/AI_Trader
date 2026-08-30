import pandas as pd
from typing import Callable, List, Dict, Any
from broker.mt5_connector import get_mt5_connector
from core.backtesting import Backtester
from core.indicators import Indicators

# Маппинг таймфреймов (строки, которые понимает get_rates)
TIMEFRAME_MAP = {
    'M5': 'M5',
    'M15': 'M15',
    'M30': 'M30',
    'H1': 'H1'
}


def _ensure_core_indicators(df: pd.DataFrame, include_ema_200: bool = True) -> pd.DataFrame:
    """Ensure the canonical project indicator set is available.

    The runner uses core.Indicators as the single source of truth. Existing
    strategy-specific fallback calculations are intentionally kept below for
    backward compatibility with older external callers/fixtures.
    """
    indicators = Indicators()
    return indicators.add_all(df, include_ema_200=include_ema_200)


def run_intraday_backtest(
    symbol: str,
    timeframe_str: str,
    bars: int,
    initial_balance: float,
    signal_generator: Callable[[pd.DataFrame], List[Dict[str, Any]]],
    sl_mult: float = 1.5,
    tp_mult: float = 3.0,
    risk_per_trade: float = 0.01
):
    """Universal intraday runner using the shared Backtester and Indicators."""
    if timeframe_str not in TIMEFRAME_MAP:
        raise ValueError(f"Таймфрейм {timeframe_str} не поддерживается.")

    connector = get_mt5_connector()
    if not connector.connect():
        print("[!] Ошибка подключения к MT5. Проверь config.py")
        return None

    try:
        print(f"[*] Загрузка {bars} баров для {symbol} ({timeframe_str})...")
        df = connector.get_rates(symbol, timeframe_str, bars)

        if df.empty:
            print("[!] Не удалось получить данные.")
            return None

        # Canonical indicator calculation shared by all strategies/runners.
        df = _ensure_core_indicators(df, include_ema_200=True)

        print("[*] Генерация сигналов стратегии...")
        signals = signal_generator(df)
        print(f"[*] Найдено {len(signals)} потенциальных сделок.")

        backtester = Backtester(
            initial_balance=initial_balance,
            risk_per_trade=risk_per_trade,
            atr_sl_multiplier=sl_mult,
            atr_tp_multiplier=tp_mult
        )

        return backtester.run(df, connector, signals, symbol)
    finally:
        connector.disconnect()


def test_multiple_timeframes(
    symbol: str,
    timeframes: list[str],
    bars: int,
    initial_balance: float,
    signal_generator: Callable,
    risk_per_trade: float = 0.01
):
    """Run the same strategy through the shared runner on multiple timeframes."""
    results = {}
    for tf in timeframes:
        print(f"\n{'=' * 60}")
        print(f"ТЕСТ НА ТАЙМФРЕЙМЕ: {tf}")
        print(f"{'=' * 60}")
        stats = run_intraday_backtest(
            symbol=symbol,
            timeframe_str=tf,
            bars=bars,
            initial_balance=initial_balance,
            signal_generator=signal_generator,
            sl_mult=1.0,
            tp_mult=2.0,
            risk_per_trade=risk_per_trade
        )
        if stats:
            results[tf] = stats

    print(f"\n{'=' * 60}")
    print(f"ИТОГОВОЕ СРАВНЕНИЕ ДЛЯ {symbol}:")
    print(f"{'=' * 60}")
    for tf, stats in results.items():
        print(f"{tf}: Сделок={stats['total_trades']}, Винрейт={stats['win_rate']}, "
              f"PF={stats['profit_factor']}, PnL={stats['total_pnl_rub']:.2f} RUB, "
              f"Макс.просадка={stats['max_drawdown_percent']}")
    return results


# --- Legacy helpers retained for compatibility with direct external imports. ---
def _calculate_atr_inline(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    high_low = df['high'] - df['low']
    high_close = (df['high'] - df['close'].shift()).abs()
    low_close = (df['low'] - df['close'].shift()).abs()
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = ranges.max(axis=1)
    df['atr_14'] = true_range.rolling(window=period).mean()
    return df


def _calculate_adx_inline(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    # Keep the legacy entry point, but use the canonical implementation so
    # there is no second ADX formula in the project.
    return Indicators().add_adx(df, period=period)


def run_mtf_backtest(
    symbol: str,
    main_timeframe: str,
    older_timeframe: str,
    bars_main: int,
    bars_older: int,
    initial_balance: float,
    signal_generator: Callable,
    sl_mult: float = 1.5,
    tp_mult: float = 3.0,
    risk_per_trade: float = 0.01
):
    """Run a multi-timeframe backtest using canonical indicators."""
    connector = get_mt5_connector()
    if not connector.connect():
        print("[!] Ошибка подключения к MT5")
        return None

    try:
        print(f"[*] Загрузка MTF данных для {symbol}: {main_timeframe} + {older_timeframe}")
        df_main = connector.get_rates(symbol, main_timeframe, bars_main)
        df_older = connector.get_rates(symbol, older_timeframe, bars_older)

        if df_main.empty or df_older.empty:
            print("[!] Не удалось получить данные")
            return None

        df_main = _ensure_core_indicators(df_main, include_ema_200=True)
        df_older = _ensure_core_indicators(df_older, include_ema_200=True)

        print("[*] Генерация MTF сигналов...")
        signals = signal_generator(df_main, df_older)
        print(f"[*] Найдено {len(signals)} сигналов")

        backtester = Backtester(
            initial_balance=initial_balance,
            risk_per_trade=risk_per_trade,
            atr_sl_multiplier=sl_mult,
            atr_tp_multiplier=tp_mult
        )

        return backtester.run(df_main, connector, signals, symbol)
    finally:
        connector.disconnect()
