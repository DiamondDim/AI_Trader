# run_massive_test_interactive.py
"""
Интерактивный скрипт для массового тестирования интрадей-стратегий
с возможностью выбора символов, стратегий и таймфреймов.
"""
import MetaTrader5 as mt5
import config
import sys
from datetime import datetime
from typing import List, Dict, Any
from broker.mt5_connector import get_mt5_connector
from strategy_intraday.test_intraday import run_intraday_backtest, run_mtf_backtest

# Импорты стратегий
from strategy_intraday.ema_pullback import generate_ema_pullback_signals
from strategy_intraday.london_breakout import generate_london_breakout_signals
from strategy_intraday.elder_triple_screen import generate_elder_signals


def get_available_symbols():
    """Получает список доступных форекс-пар из MT5."""
    if not mt5.initialize():
        print(f"❌ Ошибка инициализации MT5: {mt5.last_error()}")
        return []

    if not mt5.login(config.MT5_LOGIN, config.MT5_PASSWORD, config.MT5_SERVER):
        print(f"❌ Ошибка логина: {mt5.last_error()}")
        mt5.shutdown()
        return []

    print("✅ Подключение успешно!\n")

    all_symbols = mt5.symbols_get()
    major_currencies = ['EUR', 'USD', 'GBP', 'JPY', 'CHF', 'AUD', 'CAD', 'NZD']
    forex_pairs = []

    for symbol in all_symbols:
        name = symbol.name
        if any(curr in name for curr in major_currencies):
            if not any(exclude in name for exclude in ['XAU', 'XAG', 'BTC', 'ETH', 'LTC']):
                forex_pairs.append({
                    'name': name,
                    'description': symbol.description,
                    'spread': symbol.spread,
                    'digits': symbol.digits
                })

    mt5.shutdown()
    return forex_pairs


def display_symbols(symbols):
    """Отображает нумерованный список символов."""
    print(f"\n📊 Найдено {len(symbols)} основных валютных пар:\n")
    print("=" * 70)
    print(f"{'№':<4} {'Символ':<15} {'Описание':<30} {'Спред':<10}")
    print("=" * 70)
    for i, pair in enumerate(symbols, 1):
        print(f"{i:<4} {pair['name']:<15} {pair['description']:<30} {pair['spread']:<10}")
    print("=" * 70)


def parse_selection(input_str, total_symbols):
    """Парсит ввод пользователя и возвращает список выбранных индексов."""
    selected_indices = []
    parts = input_str.split(',')

    for part in parts:
        part = part.strip()
        if '-' in part:
            try:
                start, end = part.split('-')
                start = int(start.strip())
                end = int(end.strip())
                if 1 <= start <= total_symbols and 1 <= end <= total_symbols:
                    for i in range(start, end + 1):
                        if i not in selected_indices:
                            selected_indices.append(i)
                else:
                    print(f"⚠️ Диапазон {start}-{end} выходит за пределы списка")
            except ValueError:
                print(f"⚠️ Неверный формат диапазона: {part}")
        else:
            try:
                num = int(part)
                if 1 <= num <= total_symbols:
                    if num not in selected_indices:
                        selected_indices.append(num)
                else:
                    print(f"⚠️ Номер {num} выходит за пределы списка (1-{total_symbols})")
            except ValueError:
                print(f"⚠️ Неверный номер: {part}")

    return sorted(selected_indices)


def select_symbols(symbols):
    """Интерактивный выбор символов."""
    while True:
        print("\n🎯 Выберите одну или несколько пар для тестирования:")
        print("   Введите номера через запятую (например: 1,3,5)")
        print("   Или диапазон (например: 1-5)")
        print("   Или комбинацию (например: 1,3,5-8)")
        print("   Введите 'all' для выбора всех пар")
        print("   Введите 'q' для выхода\n")

        user_input = input("Ваш выбор: ").strip().lower()

        if user_input == 'q':
            print("Выход из программы.")
            return []

        if user_input == 'all':
            print(f"✅ Выбраны все {len(symbols)} пар")
            return list(range(1, len(symbols) + 1))

        selected_indices = parse_selection(user_input, len(symbols))

        if selected_indices:
            print(f"\n✅ Выбрано {len(selected_indices)} пар:")
            for idx in selected_indices:
                print(f"   {idx}. {symbols[idx - 1]['name']} - {symbols[idx - 1]['description']}")

            confirm = input("\nПодтвердить выбор? (y/n): ").strip().lower()
            if confirm == 'y':
                return selected_indices
            else:
                print("❌ Выбор отменен. Попробуйте снова.\n")
        else:
            print("❌ Не выбрано ни одной пары. Попробуйте снова.\n")


def select_strategy():
    """Интерактивный выбор стратегии."""
    strategies = {
        '1': {
            'name': 'EMA Pullback (Откат к EMA50)',
            'type': 'single_tf',
            'generator': generate_ema_pullback_signals
        },
        '2': {
            'name': 'London Breakout (Пробой азиатского диапазона)',
            'type': 'single_tf',
            'generator': generate_london_breakout_signals
        },
        '3': {
            'name': 'Elder Triple Screen (Три экрана Элдера)',
            'type': 'mtf',
            'generator': generate_elder_signals
        }
    }

    print("\n🎯 Выберите стратегию для тестирования:")
    print("=" * 70)
    for key, strat in strategies.items():
        print(f"{key}. {strat['name']}")
    print("=" * 70)

    while True:
        choice = input("\nВаш выбор (1-3): ").strip()
        if choice in strategies:
            print(f"✅ Выбрана стратегия: {strategies[choice]['name']}")
            return strategies[choice]
        else:
            print("❌ Неверный выбор. Попробуйте снова.")


def select_timeframes(is_mtf: bool):
    """Интерактивный выбор таймфреймов."""
    if is_mtf:
        print("\n🎯 Выберите таймфреймы для MTF стратегии:")
        print("   Рабочий ТФ (M15) + Старший ТФ (H1)")
        print("   Введите 'all' для тестирования на M15+H1 и M30+H1")
        print("   Или введите конкретные комбинации через запятую:")
        print("   Например: M15+H1, M30+H1")

        while True:
            choice = input("\nВаш выбор: ").strip().lower()
            if choice == 'all':
                return [('M15', 'H1'), ('M30', 'H1')]
            elif '+' in choice:
                combinations = []
                for combo in choice.split(','):
                    combo = combo.strip()
                    if '+' in combo:
                        main_tf, older_tf = combo.split('+')
                        main_tf = main_tf.strip().upper()
                        older_tf = older_tf.strip().upper()
                        if main_tf in ['M5', 'M15', 'M30'] and older_tf in ['H1', 'H4']:
                            combinations.append((main_tf, older_tf))
                        else:
                            print(f"⚠️ Неверная комбинация: {combo}")
                if combinations:
                    return combinations
            print("❌ Неверный формат. Попробуйте снова.")
    else:
        print("\n🎯 Выберите таймфреймы для тестирования:")
        print("   Введите номера через запятую (например: 1,2,3)")
        print("   Или 'all' для всех таймфреймов")
        print("   1. M5")
        print("   2. M15")
        print("   3. M30")

        while True:
            choice = input("\nВаш выбор: ").strip().lower()
            if choice == 'all':
                return ['M5', 'M15', 'M30']
            else:
                timeframes = []
                for num in choice.split(','):
                    num = num.strip()
                    if num == '1':
                        timeframes.append('M5')
                    elif num == '2':
                        timeframes.append('M15')
                    elif num == '3':
                        timeframes.append('M30')
                if timeframes:
                    return timeframes
            print("❌ Неверный выбор. Попробуйте снова.")


def run_massive_test(symbols: List[str], strategy: Dict, timeframes: List, initial_balance: float = 50000.0):
    """Запускает массовое тестирование."""
    results = []
    total_tests = len(symbols) * len(timeframes)
    current_test = 0

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    results_file = f"massive_test_results_{strategy['name'].replace(' ', '_')}_{timestamp}.txt"

    print(f"\n{'=' * 80}")
    print(f"🚀 ЗАПУСК МАССОВОГО ТЕСТИРОВАНИЯ")
    print(f"Стратегия: {strategy['name']}")
    print(f"Всего тестов: {total_tests}")
    print(f"Депозит: {initial_balance} RUB")
    print(f"Результаты будут сохранены в: {results_file}")
    print(f"{'=' * 80}\n")

    # Инициализируем файл результатов
    with open(results_file, 'w', encoding='utf-8') as f:
        f.write(f"{'=' * 100}\n")
        f.write(f"РЕЗУЛЬТАТЫ МАССОВОГО ТЕСТИРОВАНИЯ\n")
        f.write(f"Дата: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Стратегия: {strategy['name']}\n")
        f.write(f"Депозит: {initial_balance} RUB\n")
        f.write(f"{'=' * 100}\n\n")

    for symbol in symbols:
        for tf_config in timeframes:
            current_test += 1
            progress = (current_test / total_tests) * 100

            if strategy['type'] == 'mtf':
                main_tf, older_tf = tf_config
                tf_label = f"{main_tf}+{older_tf}"
            else:
                tf_label = tf_config

            print(f"[{current_test}/{total_tests}] ({progress:.1f}%) Тестируем {symbol} на {tf_label}...", end=' ',
                  flush=True)

            try:
                if strategy['type'] == 'mtf':
                    main_tf, older_tf = tf_config
                    stats = run_mtf_backtest(
                        symbol=symbol,
                        main_timeframe=main_tf,
                        older_timeframe=older_tf,
                        bars_main=5000,
                        bars_older=2000,
                        initial_balance=initial_balance,
                        signal_generator=strategy['generator'],
                        sl_mult=1.5,
                        tp_mult=3.0
                    )
                else:
                    stats = run_intraday_backtest(
                        symbol=symbol,
                        timeframe_str=tf_config,
                        bars=5000,
                        initial_balance=initial_balance,
                        signal_generator=strategy['generator'],
                        sl_mult=1.0,
                        tp_mult=2.0
                    )

                if stats:
                    result = {
                        'symbol': symbol,
                        'timeframe': tf_label,
                        'total_trades': stats['total_trades'],
                        'win_rate': float(stats['win_rate'].replace('%', '')),
                        'profit_factor': float(stats['profit_factor']) if stats['profit_factor'] != 'inf' else 999.99,
                        'pnl_rub': stats['total_pnl_rub'],
                        'max_drawdown_percent': float(stats['max_drawdown_percent'].replace('%', ''))
                    }
                    results.append(result)

                    # Сохраняем в файл
                    with open(results_file, 'a', encoding='utf-8') as f:
                        f.write(f"{symbol:<15} | {tf_label:<10} | Сделок: {result['total_trades']:<5} | "
                                f"Винрейт: {result['win_rate']:.2f}% | PF: {result['profit_factor']:.2f} | "
                                f"PnL: {result['pnl_rub']:.2f} RUB | Просадка: {result['max_drawdown_percent']:.2f}%\n")

                    print(f"✅ WR={result['win_rate']:.1f}%, PF={result['profit_factor']:.2f}")
                else:
                    print("❌ Нет данных")

            except Exception as e:
                print(f"❌ Ошибка: {e}")
                continue

    # Финальная сортировка и сохранение
    valid_results = [r for r in results if r['total_trades'] > 0]
    sorted_results = sorted(valid_results, key=lambda x: x['profit_factor'], reverse=True)

    with open(results_file, 'a', encoding='utf-8') as f:
        f.write(f"\n{'=' * 100}\n")
        f.write(f"🏆 ТОП-30 ЛУЧШИХ РЕЗУЛЬТАТОВ:\n")
        f.write(f"{'=' * 100}\n")
        f.write(
            f"{'№':<4} {'Символ':<15} {'ТФ':<10} {'Сделок':<8} {'Винрейт':<10} {'PF':<8} {'PnL (RUB)':<12} {'Просадка':<10}\n")
        f.write(f"{'-' * 100}\n")

        for idx, res in enumerate(sorted_results[:30], 1):
            f.write(f"{idx:<4} {res['symbol']:<15} {res['timeframe']:<10} "
                    f"{res['total_trades']:<8} {res['win_rate']:<10.2f} "
                    f"{res['profit_factor']:<8.2f} {res['pnl_rub']:<12.2f} "
                    f"{res['max_drawdown_percent']:<10.2f}\n")

    print(f"\n{'=' * 80}")
    print(f"✅ МАССОВОЕ ТЕСТИРОВАНИЕ ЗАВЕРШЕНО")
    print(f"Результаты сохранены в: {results_file}")
    print(f"{'=' * 80}")

    return results


def main():
    print("🔍 Подключаемся к MT5 для получения списка символов...\n")
    symbols = get_available_symbols()

    if not symbols:
        print("❌ Не удалось получить список символов.")
        return

    # Отображаем список
    display_symbols(symbols)

    # Выбор символов
    selected_indices = select_symbols(symbols)
    if not selected_indices:
        return

    selected_symbols = [symbols[idx - 1]['name'] for idx in selected_indices]

    # Выбор стратегии
    strategy = select_strategy()

    # Выбор таймфреймов
    is_mtf = strategy['type'] == 'mtf'
    timeframes = select_timeframes(is_mtf)

    # Депозит
    print("\n💰 Введите начальный депозит (по умолчанию 50000 RUB):")
    balance_input = input().strip()
    try:
        initial_balance = float(balance_input) if balance_input else 50000.0
    except ValueError:
        print("⚠️ Неверный формат, используем 50000 RUB")
        initial_balance = 50000.0

    # Запускаем тест
    run_massive_test(selected_symbols, strategy, timeframes, initial_balance)


if __name__ == "__main__":
    main()
