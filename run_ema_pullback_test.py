"""
Тестирование стратегии EMA Pullback на выбранных символах и таймфреймах.
Использует list_symbols.py для интерактивного выбора символов.
Поддерживает выбор риска на сделку.
"""
import sys
import os
from datetime import datetime
from typing import List

# Добавляем корень проекта в путь
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from list_symbols import get_available_symbols, display_symbols, select_symbols
from strategy_intraday.test_intraday import run_intraday_backtest
from strategy_intraday.ema_pullback import generate_ema_pullback_signals


def select_timeframes() -> List[str]:
    """Интерактивный выбор таймфреймов"""
    print("\n" + "=" * 70)
    print("🎯 Выберите таймфреймы для тестирования:")
    print("=" * 70)
    print("1. M5")
    print("2. M15")
    print("3. M30")
    print("4. H1")
    print("5. Все интрадей (M5, M15, M30)")
    print("6. Все включая H1 (M5, M15, M30, H1)")
    print("=" * 70)

    while True:
        choice = input("\nВаш выбор (1-6): ").strip()
        if choice == '1':
            return ['M5']
        elif choice == '2':
            return ['M15']
        elif choice == '3':
            return ['M30']
        elif choice == '4':
            return ['H1']
        elif choice == '5':
            return ['M5', 'M15', 'M30']
        elif choice == '6':
            return ['M5', 'M15', 'M30', 'H1']
        else:
            print("❌ Неверный выбор. Попробуйте снова.")


def select_risk() -> float:
    """Интерактивный выбор риска на сделку"""
    print("\n" + "=" * 70)
    print("💰 Выберите риск на сделку (в процентах):")
    print("=" * 70)
    print("1. Консервативный: 0.5% (минимальный риск)")
    print("2. Стандартный: 1.0% (рекомендуется)")
    print("3. Умеренный: 1.5%")
    print("4. Агрессивный: 2.0%")
    print("5. Очень агрессивный: 2.5%")
    print("6. Свой вариант (введите число)")
    print("=" * 70)

    while True:
        choice = input("\nВаш выбор (1-6): ").strip()

        if choice == '1':
            return 0.005
        elif choice == '2':
            return 0.01
        elif choice == '3':
            return 0.015
        elif choice == '4':
            return 0.02
        elif choice == '5':
            return 0.025
        elif choice == '6':
            while True:
                custom = input("Введите риск в процентах (например, 1.5): ").strip()
                try:
                    risk = float(custom) / 100.0
                    if 0.001 <= risk <= 0.10:  # От 0.1% до 10%
                        return risk
                    else:
                        print("⚠️ Риск должен быть от 0.1% до 10%")
                except ValueError:
                    print("❌ Неверный формат. Введите число.")
        else:
            print("❌ Неверный выбор. Попробуйте снова.")


def run_test_for_symbol(symbol: str, timeframes: List[str], bars: int,
                        initial_balance: float, risk_per_trade: float):
    """Запускает тест для одного символа на всех выбранных таймфреймах"""
    print(f"\n{'=' * 70}")
    print(f"🔬 ТЕСТИРОВАНИЕ: {symbol}")
    print(f"Риск на сделку: {risk_per_trade * 100:.2f}%")
    print(f"{'=' * 70}")

    results = {}
    for tf in timeframes:
        print(f"\n[*] Таймфрейм: {tf}")
        stats = run_intraday_backtest(
            symbol=symbol,
            timeframe_str=tf,
            bars=bars,
            initial_balance=initial_balance,
            signal_generator=generate_ema_pullback_signals,
            sl_mult=1.0,  # Параметры для интрадея
            tp_mult=2.0,
            risk_per_trade=risk_per_trade  # <-- ПЕРЕДАЕМ РИСК
        )
        if stats:
            results[tf] = stats
            print(f"✅ Сделок: {stats['total_trades']}, Винрейт: {stats['win_rate']}, "
                  f"PF: {stats['profit_factor']}, PnL: {stats['total_pnl_rub']:.2f} RUB")
        else:
            print(f"❌ Не удалось получить результаты для {tf}")
    return results


def save_results(all_results: dict, risk_per_trade: float,
                 filename: str = "ema_pullback_test_results.txt"):
    """Сохраняет результаты в файл"""
    with open(filename, 'w', encoding='utf-8') as f:
        f.write("=" * 100 + "\n")
        f.write("РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ EMA PULLBACK\n")
        f.write(f"Дата: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Риск на сделку: {risk_per_trade * 100:.2f}%\n")
        f.write("=" * 100 + "\n\n")

        # Фильтруем пары с 0 сделок и сортируем
        all_tests = []
        for symbol, tf_results in all_results.items():
            for tf, stats in tf_results.items():
                if stats['total_trades'] > 0:
                    all_tests.append({
                        'symbol': symbol,
                        'timeframe': tf,
                        'stats': stats
                    })

        def get_pf(x):
            pf = x['stats']['profit_factor']
            return float(pf) if pf != 'inf' else 999.99

        all_tests.sort(key=get_pf, reverse=True)

        # Топ-20 лучших
        f.write("🏆 ТОП-20 ЛУЧШИХ РЕЗУЛЬТАТОВ:\n")
        f.write("-" * 100 + "\n")
        f.write(
            f"{'№':<4} {'Символ':<15} {'ТФ':<5} {'Сделок':<8} {'Винрейт':<10} {'PF':<8} {'PnL (RUB)':<12} {'Просадка':<10}\n")
        f.write("-" * 100 + "\n")

        for idx, test in enumerate(all_tests[:20], 1):
            stats = test['stats']
            f.write(f"{idx:<4} {test['symbol']:<15} {test['timeframe']:<5} "
                    f"{stats['total_trades']:<8} {stats['win_rate']:<10} "
                    f"{stats['profit_factor']:<8} {stats['total_pnl_rub']:<12.2f} "
                    f"{stats['max_drawdown_percent']:<10}\n")

        f.write("\n" + "=" * 100 + "\n")
        f.write("ВСЕ РЕЗУЛЬТАТЫ:\n")
        f.write("=" * 100 + "\n\n")

        for test in all_tests:
            stats = test['stats']
            f.write(f"{test['symbol']:<15} | {test['timeframe']:<5} | "
                    f"Сделок: {stats['total_trades']:<5} | "
                    f"Винрейт: {stats['win_rate']} | "
                    f"PF: {stats['profit_factor']} | "
                    f"PnL: {stats['total_pnl_rub']:.2f} RUB | "
                    f"Просадка: {stats['max_drawdown_percent']}\n")

    print(f"\n✅ Результаты сохранены в: {filename}")


def main():
    print("🔍 Подключаемся к MT5 для получения списка символов...\n")

    # Получаем список символов
    symbols = get_available_symbols()
    if not symbols:
        print("❌ Не удалось получить список символов.")
        return

    # Отображаем список
    display_symbols(symbols)

    # Выбираем символы
    selected_indices = select_symbols(symbols)
    if not selected_indices:
        print("❌ Не выбрано ни одного символа.")
        return

    # Выбираем таймфреймы
    timeframes = select_timeframes()

    # === НОВЫЙ ШАГ: Выбор риска ===
    risk_per_trade = select_risk()
    print(f"\n✅ Выбран риск: {risk_per_trade * 100:.2f}%")

    print("\n💰 Введите количество баров для загрузки (по умолчанию 10000):")
    bars_input = input().strip()
    try:
        bars = int(bars_input) if bars_input else 10000
    except ValueError:
        print("⚠️ Неверный формат, используем 10000")
        bars = 10000

    print("\n💰 Введите начальный депозит (по умолчанию 10000 RUB):")
    balance_input = input().strip()
    try:
        initial_balance = float(balance_input) if balance_input else 10000.0
    except ValueError:
        print("⚠️ Неверный формат, используем 10000 RUB")
        initial_balance = 10000.0

    # Извлекаем имена выбранных символов
    selected_symbols = [symbols[idx - 1]['name'] for idx in selected_indices]

    print(f"\n{'=' * 70}")
    print(f"🚀 ЗАПУСК ТЕСТИРОВАНИЯ")
    print(f"Стратегия: EMA Pullback")
    print(f"Символов: {len(selected_symbols)}")
    print(f"Таймфреймы: {', '.join(timeframes)}")
    print(f"Риск на сделку: {risk_per_trade * 100:.2f}%")
    print(f"Баров: {bars}")
    print(f"Депозит: {initial_balance} RUB")
    print(f"{'=' * 70}")

    # Запускаем тест для каждого символа
    all_results = {}
    for symbol in selected_symbols:
        results = run_test_for_symbol(symbol, timeframes, bars, initial_balance, risk_per_trade)
        all_results[symbol] = results

    # Сохраняем результаты
    save_results(all_results, risk_per_trade)

    print(f"\n{'=' * 70}")
    print("✅ ТЕСТИРОВАНИЕ ЗАВЕРШЕНО")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    main()
