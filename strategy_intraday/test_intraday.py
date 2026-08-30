import pandas as pd
from datetime import datetime
from typing import Callable, List, Dict, Any
from broker.mt5_connector import get_mt5_connector
from core.backtesting import Backtester

# Маппинг таймфреймов (строки, которые понимает твой get_rates)
TIMEFRAME_MAP = {
    'M5': 'M5',
    'M15': 'M15',
    'M30': 'M30',
    'H1': 'H1'
}


def run_intraday_backtest(
        symbol: str,
        timeframe_str: str,
        bars: int,
        initial_balance: float,
        signal_generator: Callable[[pd.DataFrame], List[Dict[str, Any]]],
        sl_mult: float = 1.5,
        tp_mult: float = 3.0,
        risk_per_trade: float = 0.01  # <-- Риск на сделку (по умолчанию 1%)
):
    """Универсальный раннер, адаптированный под твой Backtester"""
    if timeframe_str not in TIMEFRAME_MAP:
        raise ValueError(f"Таймфрейм {timeframe_str} не поддерживается.")

    connector = get_mt5_connector()
    if not connector.connect():
        print("[!] Ошибка подключения к MT5. Проверь config.py")
        return None

    print(f"[*] Загрузка {bars} баров для {symbol} ({timeframe_str})...")
    df = connector.get_rates(symbol, timeframe_str, bars)

    if df.empty:
        print("[!] Не удалось получить данные.")
        connector.disconnect()
        return None

    # === ГАРАНТИЯ НАЛИЧИЯ КОЛОНОК ДЛЯ ТВОЕГО BACKTESTER ===
    if 'atr_14' not in df.columns:
        df = _calculate_atr_inline(df, 14)
    if 'adx_14' not in df.columns:
        df = _calculate_adx_inline(df, 14)

    print(f"[*] Генерация сигналов стратегии...")
    signals = signal_generator(df)
    print(f"[*] Найдено {len(signals)} потенциальных сделок.")

    # Инициализируем твой продвинутый бэктестер
    backtester = Backtester(
        initial_balance=initial_balance,
        risk_per_trade=risk_per_trade,  # <-- ИСПОЛЬЗУЕМ ПЕРЕДАННЫЙ РИСК
        atr_sl_multiplier=sl_mult,
        atr_tp_multiplier=tp_mult
    )

    # Запускаем тест
    stats = backtester.run(df, connector, signals, symbol)
    connector.disconnect()
    return stats


def test_multiple_timeframes(
        symbol: str,
        timeframes: list[str],
        bars: int,
        initial_balance: float,
        signal_generator: Callable,
        risk_per_trade: float = 0.01  # <-- НОВЫЙ ПАРАМЕТР
):
    """Прогоняет стратегию на нескольких таймфреймах"""
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
            risk_per_trade=risk_per_trade  # <-- ИСПРАВЛЕНО: убран пробел
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


# --- Встроенные помощники на случай, если core.indicators пуст ---
def _calculate_atr_inline(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    high_low = df['high'] - df['low']
    high_close = (df['high'] - df['close'].shift()).abs()
    low_close = (df['low'] - df['close'].shift()).abs()
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = ranges.max(axis=1)
    df['atr_14'] = true_range.rolling(window=period).mean()
    return df


def _calculate_adx_inline(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    # Упрощенный расчет ADX для бэктеста (достаточный для фильтрации)
    up_move = df['high'] - df['high'].shift(1)
    down_move = df['low'].shift(1) - df['low']
    pos_dm = ((up_move > down_move) & (up_move > 0)) * up_move
    neg_dm = ((down_move > up_move) & (down_move > 0)) * down_move

    tr = pd.concat(
        [df['high'] - df['low'], (df['high'] - df['close'].shift()).abs(),
         (df['low'] - df['close'].shift()).abs()],
        axis=1).max(axis=1)
    atr = tr.rolling(window=period).mean()

    pos_di = 100 * (pos_dm.rolling(window=period).mean() / atr)
    neg_di = 100 * (neg_dm.rolling(window=period).mean() / atr)

    dx = 100 * (pos_di - neg_di).abs() / (pos_di + neg_di)
    df['adx_14'] = dx.rolling(window=period).mean()
    return df


def run_mtf_backtest(
        symbol: str,
        main_timeframe: str,  # Рабочий ТФ (M15)
        older_timeframe: str,  # Старший ТФ (H1)
        bars_main: int,
        bars_older: int,
        initial_balance: float,
        signal_generator: callable,  # Функция принимает (df_main, df_older)
        sl_mult: float = 1.5,
        tp_mult: float = 3.0,
        risk_per_trade: float = 0.01  # <-- НОВЫЙ ПАРАМЕТР
):
    """Запуск бэктеста с мульти-таймфреймовым анализом"""
    connector = get_mt5_connector()
    if not connector.connect():
        print("[!] Ошибка подключения к MT5")
        return None

    print(f"[*] Загрузка MTF данных для {symbol}: {main_timeframe} + {older_timeframe}")
    df_main = connector.get_rates(symbol, main_timeframe, bars_main)
    df_older = connector.get_rates(symbol, older_timeframe, bars_older)

    if df_main.empty or df_older.empty:
        print("[!] Не удалось получить данные")
        connector.disconnect()
        return None

    # === КРИТИЧЕСКИЙ ФИКС: рассчитываем ATR на рабочем ТФ ДО передачи в бэктестер ===
    if 'atr_14' not in df_main.columns:
        print("[*] Рассчитываем ATR(14) на рабочем таймфрейме...")
        tr = pd.concat([
            df_main['high'] - df_main['low'],
            (df_main['high'] - df_main['close'].shift()).abs(),
            (df_main['low'] - df_main['close'].shift()).abs()
        ], axis=1).max(axis=1)
        df_main['atr_14'] = tr.rolling(window=14).mean()

    print(f"[*] Генерация MTF сигналов...")
    signals = signal_generator(df_main, df_older)
    print(f"[*] Найдено {len(signals)} сигналов")

    backtester = Backtester(
        initial_balance=initial_balance,
        risk_per_trade=risk_per_trade,  # <-- ИСПОЛЬЗУЕМ ПЕРЕДАННЫЙ РИСК
        atr_sl_multiplier=sl_mult,
        atr_tp_multiplier=tp_mult
    )

    # Бэктестер работает на df_main (рабочий ТФ)
    stats = backtester.run(df_main, connector, signals, symbol)
    connector.disconnect()
    return stats
