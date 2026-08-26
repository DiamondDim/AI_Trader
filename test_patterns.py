import config
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from broker.mt5_connector import get_mt5_connector
from core.pattern_detector import PatternDetector
from core.patterns.candlestick import BullishEngulfing, BearishEngulfing, Doji, Hammer
from core.backtesting import Backtester
from core.indicators import Indicators
from utils.helpers import is_active_session
import pandas as pd


def main():
    # Читаем символ из аргументов командной строки
    if len(sys.argv) > 1:
        symbol = sys.argv[1]
    else:
        symbol = config.SYMBOL

    print(f"🔍 Тестирование стратегии для {symbol} с фильтрами...")
    connector = get_mt5_connector()

    if connector.connect():
        print(f" Загружаем данные для {symbol} (H1)...")
        df = connector.get_rates(symbol, timeframe='H1', bars=5000)

        if df.empty:
            print("❌ Данные не получены.")
            connector.disconnect()
            return

        # 1. Добавляем индикаторы
        indicator = Indicators()
        df = indicator.add_ema(df, period=50)
        df = indicator.add_atr(df, period=14)
        df = indicator.add_stochastic(df, k_period=14, d_period=3, smooth=3)
        df = indicator.add_adx(df, period=14)

        # 2. Инициализируем детектор (только 4 проверенных паттерна)
        detector = PatternDetector()
        detector.register_pattern(BullishEngulfing())
        detector.register_pattern(BearishEngulfing())
        detector.register_pattern(Doji())
        detector.register_pattern(Hammer())

        # 3. Сканируем рынок
        print("🧠 Сканирование свечей...")
        results = detector.scan(df)

        # 4. Собираем сигналы и ПРИМЕНЯЕМ ФИЛЬТРЫ
        all_signals = []
        filtered_signals = []

        # Счетчики для статистики
        filtered_by_adx = 0
        filtered_by_stoch = 0

        for pattern_name, detections in results.items():
            for det in detections:
                det['pattern_name'] = pattern_name
                all_signals.append(det)

                idx = det['index']
                signal_type = det['type']
                signal_time = det['time']

                # Фильтр 0: Игнорируем нейтральные сигналы (Doji)
                if signal_type == 'neutral':
                    continue

                # Фильтр 1: Тренд (EMA 50)
                if signal_type == 'bullish' and df['close'].iloc[idx] <= df['ema_50'].iloc[idx]:
                    continue
                if signal_type == 'bearish' and df['close'].iloc[idx] >= df['ema_50'].iloc[idx]:
                    continue

                # Фильтр 2: Сила тренда (ADX > 20)
                adx_value = df['adx'].iloc[idx]
                if pd.isna(adx_value) or adx_value < 20:
                    filtered_by_adx += 1
                    continue

                # Фильтр 3: Stochastic (зона перекупленности/перепроданности)
                stoch_k = df['stoch_k'].iloc[idx]
                if pd.isna(stoch_k):
                    continue
                if signal_type == 'bullish' and stoch_k >= 30:
                    filtered_by_stoch += 1
                    continue
                if signal_type == 'bearish' and stoch_k <= 70:
                    filtered_by_stoch += 1
                    continue

                # Фильтр 4: Активная сессия (10:00 - 23:00 МСК)
                if not is_active_session(signal_time):
                    continue

                filtered_signals.append(det)

        print(f"\n📊 Статистика фильтрации:")
        print(f"   Всего сырых сигналов: {len(all_signals)}")
        print(f"   Отсечено по ADX (< 20): {filtered_by_adx}")
        print(f"   Отсечено по Stochastic: {filtered_by_stoch}")
        print(f"✅ Сигналов после ВСЕЙ фильтрации: {len(filtered_signals)}\n")

        # 5. Запускаем бэктестер с ДИНАМИЧЕСКИМ расчетом лота
        if filtered_signals:
            print("🚀 Запуск бэктестинга с динамическим лотом (1% риска)...")
            backtester = Backtester(
                initial_balance=10000.0,
                risk_per_trade=0.01,  # 1% риска на сделку
                atr_sl_multiplier=1.5,
                atr_tp_multiplier=3.0
            )
            stats = backtester.run(df, connector, filtered_signals, symbol=symbol)

            print("\n" + "=" * 60)
            print(" 💰 РЕЗУЛЬТАТЫ БЭКТЕСТА (ДИНАМИЧЕСКИЙ ЛОТ)")
            print("=" * 60)
            print(f"Всего сделок: {stats['total_trades']}")
            print(f"Прибыльных (TP): {stats['wins']}")
            print(f"Убыточных (SL): {stats['losses']}")
            print(f"Нейтральных (таймаут): {stats['neutrals']}")
            print(f"⚠️ Пропущено сделок (лот < мин): {stats['skipped_trades']}")
            print(f"Винрейт: {stats['win_rate']}")
            print(f"Profit Factor: {stats['profit_factor']}")
            print(f"Чистый профит: {stats['total_pnl_rub']:.2f} RUB")
            print(f"Валовая прибыль: {stats['gross_profit']:.2f} RUB")
            print(f"Валовый убыток: {stats['gross_loss']:.2f} RUB")
            print(f"Средний PnL на сделку: {stats['avg_pnl_per_trade']:.2f} RUB")
            print(f"Средний лот: {stats['avg_lot']:.4f}")
            print(f"Максимальная просадка: {stats['max_drawdown']:.2f} RUB ({stats['max_drawdown_percent']})")
            print(f"Итоговый баланс: {stats['final_balance']:.2f} RUB")
            print("=" * 60)
        else:
            print("️ После фильтрации не осталось ни одного сигнала.")

        connector.disconnect()
        print(" Тест завершен.")
    else:
        print("❌ Ошибка подключения к MT5.")


if __name__ == "__main__":
    main()
