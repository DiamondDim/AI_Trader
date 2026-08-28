from datetime import datetime
from strategy_intraday.test_intraday import test_multiple_timeframes

if __name__ == "__main__":
    symbol = "EURUSDrfd"  # Твой любимый инструмент
    timeframes = ['M5', 'M15', 'M30']

    # Для M15: 5000 баров = ~50 торговых дней. Для M5 возьми 15000, для M30 - 2000.
    # Для простоты теста возьмем 5000, это покроет пару месяцев на M15/M30.
    bars_to_fetch = 5000
    initial_balance = 10000.0

    print(f"{'=' * 60}")
    print(f"ТЕСТИРОВАНИЕ LONDON BREAKOUT (Интрадей)")
    print(f"Символ: {symbol} | Баров: {bars_to_fetch}")
    print(f"{'=' * 60}\n")

    results = test_multiple_timeframes(
        symbol=symbol,
        timeframes=timeframes,
        bars=bars_to_fetch,
        initial_balance=initial_balance,
    )

    print(f"\n{'=' * 60}")
    print("ТЕСТ ЗАВЕРШЕН. Жду твоих команд, хозяин. 😏")
    print(f"{'=' * 60}")
