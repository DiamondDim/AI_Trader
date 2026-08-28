"""
Точечная оптимизация параметров SL и TP для лучших пар,
найденных в массовом тесте.
"""
import MetaTrader5 as mt5
import config
from datetime import datetime
from strategy_intraday.test_intraday import run_intraday_backtest
from strategy_intraday.ema_pullback import generate_ema_pullback_signals


def optimize_pair(symbol: str, timeframe: str, bars: int = 10000):
    """Перебирает сетку параметров SL и TP для конкретной пары"""
    print(f"\n{'=' * 80}")
    print(f"🔬 ОПТИМИЗАЦИЯ: {symbol} на {timeframe}")
    print(f"{'=' * 80}")

    # Сетки для перебора (от агрессивных до консервативных)
    sl_multipliers = [1.0, 1.2, 1.5, 1.8, 2.0]
    tp_multipliers = [1.5, 2.0, 2.5, 3.0, 3.5]

    best_result = None
    best_pf = 0.0

    # Инициализация MT5 один раз
    if not mt5.initialize():
        print("❌ Ошибка MT5")
        return

    for sl_mult in sl_multipliers:
        for tp_mult in tp_multipliers:
            # Пропускаем нелогичные комбинации (TP должен быть >= SL)
            if tp_mult < sl_mult:
                continue

            stats = run_intraday_backtest(
                symbol=symbol,
                timeframe_str=timeframe,
                bars=bars,
                initial_balance=50000.0,
                signal_generator=generate_ema_pullback_signals,
                sl_mult=sl_mult,
                tp_mult=tp_mult
            )

            if stats and stats['total_trades'] >= 10:  # Отсекаем результаты с малым кол-вом сделок
                pf = float(stats['profit_factor'])
                wr = float(stats['win_rate'].replace('%', ''))

                # Критерий отбора: PF > 1.2 и Винрейт > 45%
                if pf > 1.2 and wr > 45.0:
                    if pf > best_pf:
                        best_pf = pf
                        best_result = {
                            'sl': sl_mult,
                            'tp': tp_mult,
                            'stats': stats
                        }

    mt5.shutdown()

    if best_result:
        print(f"\n🏆 ЛУЧШИЙ РЕЗУЛЬТАТ для {symbol} {timeframe}:")
        print(f"   SL множитель: {best_result['sl']} ATR")
        print(f"   TP множитель: {best_result['tp']} ATR")
        print(f"   Сделок: {best_result['stats']['total_trades']}")
        print(f"   Винрейт: {best_result['stats']['win_rate']}")
        print(f"   Profit Factor: {best_result['stats']['profit_factor']}")
        print(f"   PnL: {best_result['stats']['total_pnl_rub']:.2f} RUB")
        print(f"   Макс. просадка: {best_result['stats']['max_drawdown_percent']}")
    else:
        print(f"\n⚠️ Не найдено стабильных комбинаций (PF>1.2 и WR>45%) для {symbol} {timeframe}")


def main():
    print("🚀 Запуск точечной оптимизации топ-пар...")

    # Наши фавориты из massive_test_results_v2.txt
    # Увеличиваем bars до 10000, чтобы получить больше сделок для статистики
    optimize_pair("GBPUSDrfd", "M15", bars=10000)
    optimize_pair("GBPAUDrfd", "M30", bars=10000)

    print(f"\n{'=' * 80}")
    print("✅ ОПТИМИЗАЦИЯ ЗАВЕРШЕНА")
    print(f"{'=' * 80}")


if __name__ == "__main__":
    main()
