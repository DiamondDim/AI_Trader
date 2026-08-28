"""
Массовое тестирование интрадей-стратегии на всех доступных форекс-парах.
Ищет инструменты, на которых стратегия показывает лучший винрейт и профит-фактор.
"""

import MetaTrader5 as mt5
import config
from datetime import datetime
from strategy_intraday.test_intraday import test_multiple_timeframes
from strategy_intraday.ema_pullback import generate_ema_pullback_signals


def get_all_forex_symbols():
    """Получает список всех форекс-пар из MT5"""
    if not mt5.initialize():
        print(f"❌ Ошибка инициализации MT5: {mt5.last_error()}")
        return []

    if not mt5.login(config.MT5_LOGIN, config.MT5_PASSWORD, config.MT5_SERVER):
        print(f"❌ Ошибка логина: {mt5.last_error()}")
        mt5.shutdown()
        return []

    print("✅ Подключение к MT5 успешно!")

    all_symbols = mt5.symbols_get()
    major_currencies = ['EUR', 'USD', 'GBP', 'JPY', 'CHF', 'AUD', 'CAD', 'NZD']
    forex_pairs = []

    for symbol in all_symbols:
        name = symbol.name
        # Фильтруем только форекс-пары с основными валютами
        if any(curr in name for curr in major_currencies):
            # Исключаем металлы и крипто
            if not any(exclude in name for exclude in ['XAU', 'XAG', 'BTC', 'ETH', 'LTC']):
                forex_pairs.append(name)

    mt5.shutdown()
    return forex_pairs


def run_massive_backtest(symbols: list[str], bars: int = 5000, initial_balance: float = 10000.0):
    """Запускает тест на всех символах и собирает результаты"""
    results = []
    total_symbols = len(symbols)

    print(f"\n{'=' * 80}")
    print(f"МАССОВОЕ ТЕСТИРОВАНИЕ: {total_symbols} символов")
    print(f"Стратегия: EMA Pullback (улучшенная)")
    print(f"Таймфреймы: M5, M15, M30")
    print(f"Баров: {bars}")
    print(f"{'=' * 80}\n")

    for idx, symbol in enumerate(symbols, 1):
        print(f"\n[{idx}/{total_symbols}] Тестируем {symbol}...")

        try:
            # Тестируем на всех таймфреймах
            tf_results = test_multiple_timeframes(
                symbol=symbol,
                timeframes=['M5', 'M15', 'M30'],
                bars=bars,
                initial_balance=initial_balance,
                signal_generator=generate_ema_pullback_signals
            )

            # Собираем результаты для каждого таймфрейма
            for tf, stats in tf_results.items():
                results.append({
                    'symbol': symbol,
                    'timeframe': tf,
                    'total_trades': stats['total_trades'],
                    'win_rate': float(stats['win_rate'].replace('%', '')),
                    'profit_factor': float(stats['profit_factor']),
                    'pnl_rub': stats['total_pnl_rub'],
                    'max_drawdown_percent': float(stats['max_drawdown_percent'].replace('%', ''))
                })

        except Exception as e:
            print(f"❌ Ошибка при тестировании {symbol}: {e}")
            continue

    return results


def save_results_to_file(results: list[dict], filename: str = "massive_test_results.txt"):
    """Сохраняет результаты в файл"""
    # Сортируем по профит-фактору (убывание)
    sorted_results = sorted(results, key=lambda x: x['profit_factor'], reverse=True)

    with open(filename, 'w', encoding='utf-8') as f:
        f.write("=" * 100 + "\n")
        f.write("РЕЗУЛЬТАТЫ МАССОВОГО ТЕСТИРОВАНИЯ ИНТРАДЕЙ-СТРАТЕГИИ\n")
        f.write(f"Дата: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("Стратегия: EMA Pullback (улучшенная версия)\n")
        f.write("=" * 100 + "\n\n")

        # Топ-20 лучших результатов
        f.write("🏆 ТОП-20 ЛУЧШИХ РЕЗУЛЬТАТОВ (по Profit Factor):\n")
        f.write("-" * 100 + "\n")
        f.write(
            f"{'№':<4} {'Символ':<15} {'ТФ':<5} {'Сделок':<8} {'Винрейт':<10} {'PF':<8} {'PnL (RUB)':<12} {'Просадка':<10}\n")
        f.write("-" * 100 + "\n")

        for idx, res in enumerate(sorted_results[:20], 1):
            f.write(f"{idx:<4} {res['symbol']:<15} {res['timeframe']:<5} "
                    f"{res['total_trades']:<8} {res['win_rate']:<10.2f} "
                    f"{res['profit_factor']:<8.2f} {res['pnl_rub']:<12.2f} "
                    f"{res['max_drawdown_percent']:<10.2f}\n")

        f.write("\n" + "=" * 100 + "\n")
        f.write("ВСЕ РЕЗУЛЬТАТЫ:\n")
        f.write("=" * 100 + "\n\n")

        # Все результаты
        for res in sorted_results:
            f.write(f"{res['symbol']:<15} | {res['timeframe']:<5} | "
                    f"Сделок: {res['total_trades']:<5} | "
                    f"Винрейт: {res['win_rate']:.2f}% | "
                    f"PF: {res['profit_factor']:.2f} | "
                    f"PnL: {res['pnl_rub']:.2f} RUB | "
                    f"Просадка: {res['max_drawdown_percent']:.2f}%\n")

    print(f"\n✅ Результаты сохранены в файл: {filename}")


def print_top_results(results: list[dict], top_n: int = 10):
    """Выводит топ-N результатов в консоль"""
    sorted_results = sorted(results, key=lambda x: x['profit_factor'], reverse=True)

    print(f"\n{'=' * 100}")
    print(f"🏆 ТОП-{top_n} ЛУЧШИХ РЕЗУЛЬТАТОВ (по Profit Factor):")
    print(f"{'=' * 100}")
    print(
        f"{'№':<4} {'Символ':<15} {'ТФ':<5} {'Сделок':<8} {'Винрейт':<10} {'PF':<8} {'PnL (RUB)':<12} {'Просадка':<10}")
    print(f"{'-' * 100}")

    for idx, res in enumerate(sorted_results[:top_n], 1):
        print(f"{idx:<4} {res['symbol']:<15} {res['timeframe']:<5} "
              f"{res['total_trades']:<8} {res['win_rate']:<10.2f} "
              f"{res['profit_factor']:<8.2f} {res['pnl_rub']:<12.2f} "
              f"{res['max_drawdown_percent']:<10.2f}")

    print(f"{'=' * 100}")


def main():
    print("🔍 Получаем список всех форекс-пар из MT5...")
    symbols = get_all_forex_symbols()

    if not symbols:
        print("❌ Не удалось получить список символов.")
        return

    print(f"✅ Найдено {len(symbols)} форекс-пар")
    print(f"📋 Список: {', '.join(symbols[:10])}{'...' if len(symbols) > 10 else ''}")

    # Параметры теста
    bars_to_fetch = 5000  # Для M15 это ~50 торговых дней
    initial_balance = 10000.0

    # Запускаем массовый тест
    results = run_massive_backtest(
        symbols=symbols,
        bars=bars_to_fetch,
        initial_balance=initial_balance
    )

    # Выводим топ-10 в консоль
    print_top_results(results, top_n=10)

    # Сохраняем все результаты в файл
    save_results_to_file(results)

    print(f"\n{'=' * 100}")
    print("✅ МАССОВОЕ ТЕСТИРОВАНИЕ ЗАВЕРШЕНО")
    print(f"{'=' * 100}")


if __name__ == "__main__":
    main()
