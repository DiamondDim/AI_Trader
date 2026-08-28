# run_massive_test_v2.py
"""
Массовое тестирование интрадей-стратегии на ВСЕХ доступных форекс-парах.
С фильтром активной сессии и сохранением промежуточных результатов.
"""

import MetaTrader5 as mt5
import config
from datetime import datetime
import time as time_module
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
    major_currencies = ['EUR', 'USD', 'GBP', 'JPY', 'CHF', 'AUD', 'CAD', 'NZD', 'RUB', 'SEK', 'NOK', 'DKK', 'TRY',
                        'ILS', 'ZAR', 'MXN', 'CNY', 'SGD']
    forex_pairs = []

    for symbol in all_symbols:
        name = symbol.name
        # Фильтруем только форекс-пары
        if any(curr in name for curr in major_currencies):
            # Исключаем металлы и крипто
            if not any(exclude in name for exclude in ['XAU', 'XAG', 'BTC', 'ETH', 'LTC', 'XPD', 'XPT']):
                forex_pairs.append(name)

    mt5.shutdown()
    return sorted(forex_pairs)


def run_massive_backtest_with_progress(symbols: list[str], bars: int = 5000, initial_balance: float = 50000.0):
    """Запускает тест на всех символах с отображением прогресса"""
    results = []
    total_symbols = len(symbols)
    results_file = "massive_test_results_v2.txt"

    print(f"\n{'=' * 80}")
    print(f"🔥 МАССОВОЕ ТЕСТИРОВАНИЕ С ФИЛЬТРОМ СЕССИИ")
    print(f"Всего символов: {total_symbols}")
    print(f"Стратегия: EMA Pullback (с фильтром 10:00-13:00 и 15:30-18:00 МСК)")
    print(f"Таймфреймы: M15, M30 (M5 пропускаем для экономии времени)")
    print(f"Депозит: {initial_balance} RUB")
    print(f"Баров: {bars}")
    print(f"{'=' * 80}\n")

    # Инициализируем файл результатов
    with open(results_file, 'w', encoding='utf-8') as f:
        f.write("=" * 100 + "\n")
        f.write("РЕЗУЛЬТАТЫ МАССОВОГО ТЕСТИРОВАНИЯ (С ФИЛЬТРОМ СЕССИИ)\n")
        f.write(f"Дата: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("Стратегия: EMA Pullback с фильтром активной сессии\n")
        f.write("Активная сессия: 10:00-13:00 и 15:30-18:00 МСК\n")
        f.write("=" * 100 + "\n\n")

    for idx, symbol in enumerate(symbols, 1):
        print(f"\n[{idx}/{total_symbols}] 🔍 Тестируем {symbol}...", end=' ', flush=True)
        start_time = time_module.time()

        try:
            # Тестируем только на M15 и M30 (M5 пропускаем для экономии времени)
            tf_results = test_multiple_timeframes(
                symbol=symbol,
                timeframes=['M15', 'M30'],
                bars=bars,
                initial_balance=initial_balance,
                signal_generator=generate_ema_pullback_signals
            )

            # Собираем результаты
            for tf, stats in tf_results.items():
                result = {
                    'symbol': symbol,
                    'timeframe': tf,
                    'total_trades': stats['total_trades'],
                    'win_rate': float(stats['win_rate'].replace('%', '')),
                    'profit_factor': float(stats['profit_factor']),
                    'pnl_rub': stats['total_pnl_rub'],
                    'max_drawdown_percent': float(stats['max_drawdown_percent'].replace('%', ''))
                }
                results.append(result)

                # Сохраняем в файл сразу после каждой пары
                with open(results_file, 'a', encoding='utf-8') as f:
                    f.write(f"{symbol:<15} | {tf:<5} | Сделок: {result['total_trades']:<5} | "
                            f"Винрейт: {result['win_rate']:.2f}% | PF: {result['profit_factor']:.2f} | "
                            f"PnL: {result['pnl_rub']:.2f} RUB | Просадка: {result['max_drawdown_percent']:.2f}%\n")

            elapsed = time_module.time() - start_time
            print(f"✅ Готово ({elapsed:.1f}с)")

        except Exception as e:
            print(f"❌ Ошибка: {e}")
            continue

    return results


def save_final_results(results: list[dict], filename: str = "massive_test_results_v2.txt"):
    """Сохраняет финальные отсортированные результаты"""
    # Фильтруем пары с 0 сделок
    valid_results = [r for r in results if r['total_trades'] > 0]

    # Сортируем по профит-фактору
    sorted_results = sorted(valid_results, key=lambda x: x['profit_factor'], reverse=True)

    with open(filename, 'w', encoding='utf-8') as f:
        f.write("=" * 100 + "\n")
        f.write("🏆 ФИНАЛЬНЫЕ РЕЗУЛЬТАТЫ (ТОЛЬКО ВАЛИДНЫЕ ПАРЫ)\n")
        f.write(f"Дата: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("Стратегия: EMA Pullback с фильтром активной сессии\n")
        f.write(f"Всего протестировано: {len(results)} комбинаций\n")
        f.write(f"Валидных (сделок > 0): {len(valid_results)} комбинаций\n")
        f.write("=" * 100 + "\n\n")

        # Топ-30 лучших
        f.write("🥇 ТОП-30 ЛУЧШИХ РЕЗУЛЬТАТОВ:\n")
        f.write("-" * 100 + "\n")
        f.write(
            f"{'№':<4} {'Символ':<15} {'ТФ':<5} {'Сделок':<8} {'Винрейт':<10} {'PF':<8} {'PnL (RUB)':<12} {'Просадка':<10}\n")
        f.write("-" * 100 + "\n")

        for idx, res in enumerate(sorted_results[:30], 1):
            f.write(f"{idx:<4} {res['symbol']:<15} {res['timeframe']:<5} "
                    f"{res['total_trades']:<8} {res['win_rate']:<10.2f} "
                    f"{res['profit_factor']:<8.2f} {res['pnl_rub']:<12.2f} "
                    f"{res['max_drawdown_percent']:<10.2f}\n")

        f.write("\n" + "=" * 100 + "\n")
        f.write("ВСЕ ВАЛИДНЫЕ РЕЗУЛЬТАТЫ:\n")
        f.write("=" * 100 + "\n\n")

        for res in sorted_results:
            f.write(f"{res['symbol']:<15} | {res['timeframe']:<5} | "
                    f"Сделок: {res['total_trades']:<5} | "
                    f"Винрейт: {res['win_rate']:.2f}% | "
                    f"PF: {res['profit_factor']:.2f} | "
                    f"PnL: {res['pnl_rub']:.2f} RUB | "
                    f"Просадка: {res['max_drawdown_percent']:.2f}%\n")

    print(f"\n✅ Финальные результаты сохранены в: {filename}")


def print_top_results(results: list[dict], top_n: int = 20):
    """Выводит топ-N результатов в консоль"""
    valid_results = [r for r in results if r['total_trades'] > 0]
    sorted_results = sorted(valid_results, key=lambda x: x['profit_factor'], reverse=True)

    print(f"\n{'=' * 100}")
    print(f"🏆 ТОП-{top_n} ЛУЧШИХ РЕЗУЛЬТАТОВ (только валидные пары):")
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

    # Параметры теста
    bars_to_fetch = 5000
    initial_balance = 50000.0  # Увеличили депозит, чтобы избежать скипов по мин. лоту

    # Запускаем массовый тест
    results = run_massive_backtest_with_progress(
        symbols=symbols,
        bars=bars_to_fetch,
        initial_balance=initial_balance
    )

    # Выводим топ-20 в консоль
    print_top_results(results, top_n=20)

    # Сохраняем финальные результаты
    save_final_results(results)

    print(f"\n{'=' * 100}")
    print("✅ МАССОВОЕ ТЕСТИРОВАНИЕ ЗАВЕРШЕНО")
    print(f"{'=' * 100}")


if __name__ == "__main__":
    main()
