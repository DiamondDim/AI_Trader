"""Интерактивное массовое тестирование доступных intraday-стратегий."""

from datetime import datetime
from typing import Dict, List

import MetaTrader5 as mt5
import config

from strategy_intraday.ema_pullback import generate_ema_pullback_signals
from strategy_intraday.fibonacci_pro import generate_fibonacci_pro_signals
from strategy_intraday.test_intraday import run_intraday_backtest


STRATEGIES = {
    "1": {
        "name": "EMA Pullback (Откат к EMA50)",
        "generator": generate_ema_pullback_signals,
        "sl_mult": 1.0,
        "tp_mult": 2.0,
    },
    "2": {
        "name": "Fibonacci Pro",
        "generator": generate_fibonacci_pro_signals,
        "sl_mult": 1.5,
        "tp_mult": 3.0,
    },
}


def get_available_symbols():
    """Получает список доступных форекс-пар из MT5."""
    if not mt5.initialize():
        print(f"❌ Ошибка инициализации MT5: {mt5.last_error()}")
        return []
    try:
        if not mt5.login(config.MT5_LOGIN, config.MT5_PASSWORD, config.MT5_SERVER):
            print(f"❌ Ошибка логина: {mt5.last_error()}")
            return []
        all_symbols = mt5.symbols_get() or []
        currencies = ("EUR", "USD", "GBP", "JPY", "CHF", "AUD", "CAD", "NZD")
        excluded = ("XAU", "XAG", "BTC", "ETH", "LTC")
        return [
            {
                "name": s.name,
                "description": s.description,
                "spread": s.spread,
                "digits": s.digits,
            }
            for s in all_symbols
            if any(c in s.name for c in currencies)
            and not any(x in s.name for x in excluded)
        ]
    finally:
        mt5.shutdown()


def display_symbols(symbols):
    print(f"\n📊 Найдено {len(symbols)} валютных инструментов:\n")
    print("=" * 80)
    print(f"{'№':<4} {'Символ':<15} {'Описание':<35} {'Спред':<8}")
    print("=" * 80)
    for i, pair in enumerate(symbols, 1):
        print(f"{i:<4} {pair['name']:<15} {pair['description']:<35} {pair['spread']:<8}")
    print("=" * 80)


def parse_selection(value: str, total: int) -> List[int]:
    selected = []
    for part in value.split(","):
        part = part.strip()
        try:
            if "-" in part:
                start, end = [int(x.strip()) for x in part.split("-", 1)]
                if 1 <= start <= end <= total:
                    selected.extend(range(start, end + 1))
            else:
                number = int(part)
                if 1 <= number <= total:
                    selected.append(number)
        except ValueError:
            continue
    return sorted(set(selected))


def select_symbols(symbols):
    while True:
        value = input("\nВыберите пары (1,3,5-8 / all / q): ").strip().lower()
        if value == "q":
            return []
        if value == "all":
            return list(range(1, len(symbols) + 1))
        selected = parse_selection(value, len(symbols))
        if selected:
            return selected
        print("❌ Неверный выбор.")


def select_strategy() -> Dict:
    print("\n🎯 Выберите стратегию:")
    print("1. EMA Pullback")
    print("2. Fibonacci Pro")
    while True:
        choice = input("Ваш выбор (1-2): ").strip()
        if choice in STRATEGIES:
            return STRATEGIES[choice]
        print("❌ Неверный выбор.")


def select_timeframes() -> List[str]:
    print("\n🎯 Выберите таймфреймы:")
    print("1. M5")
    print("2. M15")
    print("3. M30")
    print("4. H1")
    print("5. Все (M5, M15, M30, H1)")
    while True:
        choice = input("Ваш выбор: ").strip().lower()
        mapping = {"1": ["M5"], "2": ["M15"], "3": ["M30"], "4": ["H1"]}
        if choice == "5" or choice == "all":
            return ["M5", "M15", "M30", "H1"]
        result = []
        for item in choice.split(","):
            result.extend(mapping.get(item.strip(), []))
        if result:
            return list(dict.fromkeys(result))
        print("❌ Неверный выбор.")


def run_massive_test(symbols: List[str], strategy: Dict, timeframes: List[str],
                     initial_balance: float = 50000.0, bars: int = 5000,
                     risk_per_trade: float = 0.01):
    results = []
    total = len(symbols) * len(timeframes)
    current = 0
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_file = f"massive_test_results_{timestamp}.txt"

    print("\n" + "=" * 80)
    print("🚀 МАССОВОЕ ТЕСТИРОВАНИЕ")
    print(f"Стратегия: {strategy['name']}")
    print(f"Тестов: {total} | Баров: {bars} | Депозит: {initial_balance}")
    print("=" * 80)

    for symbol in symbols:
        for timeframe in timeframes:
            current += 1
            print(f"[{current}/{total}] {symbol} {timeframe}...", end=" ", flush=True)
            try:
                stats = run_intraday_backtest(
                    symbol=symbol,
                    timeframe_str=timeframe,
                    bars=bars,
                    initial_balance=initial_balance,
                    signal_generator=strategy["generator"],
                    sl_mult=strategy["sl_mult"],
                    tp_mult=strategy["tp_mult"],
                    risk_per_trade=risk_per_trade,
                )
                if not stats:
                    print("❌ Нет данных")
                    continue
                pf = stats["profit_factor"]
                pf_value = float(pf) if pf != "inf" else 999.99
                result = {
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "total_trades": stats["total_trades"],
                    "win_rate": stats["win_rate"],
                    "profit_factor": pf_value,
                    "pnl_rub": stats["total_pnl_rub"],
                    "max_drawdown_percent": stats["max_drawdown_percent"],
                }
                results.append(result)
                print(f"✅ WR={result['win_rate']}, PF={pf_value:.2f}")
            except Exception as exc:
                print(f"❌ {exc}")

    results.sort(key=lambda x: x["profit_factor"], reverse=True)
    with open(results_file, "w", encoding="utf-8") as f:
        f.write("=" * 100 + "\n")
        f.write("РЕЗУЛЬТАТЫ МАССОВОГО ТЕСТИРОВАНИЯ\n")
        f.write(f"Дата: {datetime.now():%Y-%m-%d %H:%M:%S}\n")
        f.write(f"Стратегия: {strategy['name']}\n")
        f.write("=" * 100 + "\n")
        for idx, result in enumerate(results, 1):
            f.write(
                f"{idx:>3}. {result['symbol']:<15} {result['timeframe']:<5} "
                f"Trades={result['total_trades']:<5} WR={result['win_rate']:<8} "
                f"PF={result['profit_factor']:<8.2f} PnL={result['pnl_rub']:.2f} "
                f"DD={result['max_drawdown_percent']}\n"
            )
    print(f"\n✅ Результаты сохранены: {results_file}")
    return results


def main():
    symbols = get_available_symbols()
    if not symbols:
        print("❌ Не удалось получить список символов.")
        return
    display_symbols(symbols)
    selected = select_symbols(symbols)
    if not selected:
        return
    strategy = select_strategy()
    timeframes = select_timeframes()

    bars_input = input("Количество баров [5000]: ").strip()
    try:
        bars = int(bars_input) if bars_input else 5000
    except ValueError:
        bars = 5000

    balance_input = input("Начальный депозит [50000]: ").strip()
    try:
        balance = float(balance_input) if balance_input else 50000.0
    except ValueError:
        balance = 50000.0

    risk_input = input("Риск на сделку % [1.0]: ").strip()
    try:
        risk = float(risk_input) / 100.0 if risk_input else 0.01
    except ValueError:
        risk = 0.01

    selected_symbols = [symbols[i - 1]["name"] for i in selected]
    run_massive_test(selected_symbols, strategy, timeframes, balance, bars, risk)


if __name__ == "__main__":
    main()
