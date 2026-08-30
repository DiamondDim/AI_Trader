from strategy_intraday.test_intraday import test_multiple_timeframes
from strategy_intraday.ema_pullback import generate_ema_pullback_signals


if __name__ == "__main__":
    symbol = "EURUSDrfd"
    timeframes = ['M5', 'M15', 'M30']
    bars_to_fetch = 5000
    initial_balance = 10000.0

    print(f"{'=' * 60}")
    print(f"ТЕСТИРОВАНИЕ EMA PULLBACK (Интрадей)")
    print(f"Символ: {symbol} | Баров: {bars_to_fetch}")
    print(f"{'=' * 60}\n")

    results = test_multiple_timeframes(
        symbol=symbol,
        timeframes=timeframes,
        bars=bars_to_fetch,
        initial_balance=initial_balance,
        signal_generator=generate_ema_pullback_signals,
        risk_per_trade=0.01,
    )

    print(f"\n{'=' * 60}")
    print("ТЕСТ ЗАВЕРШЕН")
    print(f"{'=' * 60}")
