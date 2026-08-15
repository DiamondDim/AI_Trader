import config
from broker.mt5_connector import get_mt5_connector
from core.pattern_detector import PatternDetector
from core.patterns.candlestick import BullishEngulfing, BearishEngulfing, Doji, Hammer
from core.backtesting import Backtester
from core.indicators import Indicators
from utils.helpers import is_active_session


def main():
    print("🔍 Тестирование стратегии с фильтрами...")
    connector = get_mt5_connector()

    if connector.connect():
        print(f"📥 Загружаем данные для {config.SYMBOL} (H1)...")
        df = connector.get_rates(config.SYMBOL, timeframe='H1', bars=200)  # Берем чуть больше для расчета EMA

        if df.empty:
            print("❌ Данные не получены.")
            connector.disconnect()
            return

        # 1. Добавляем индикатор тренда
        indicator = Indicators()
        df = indicator.add_ema(df, period=50)
        df = indicator.add_atr(df, period=14)

        # 2. Инициализируем детектор
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

        for pattern_name, detections in results.items():
            for det in detections:
                det['pattern_name'] = pattern_name
                all_signals.append(det)

                idx = det['index']
                signal_type = det['type']
                signal_time = det['time']

                # Фильтр 0: Игнорируем нейтральные сигналы (Doji) в этой стратегии
                if signal_type == 'neutral':
                    continue
                # Фильтр 1: Тренд (EMA 50)
                # Бычьи сигналы берем только если цена ВЫШЕ EMA
                # Медвежьи сигналы берем только если цена НИЖЕ EMA
                if signal_type == 'bullish' and df['close'].iloc[idx] <= df['ema_50'].iloc[idx]:
                    continue
                if signal_type == 'bearish' and df['close'].iloc[idx] >= df['ema_50'].iloc[idx]:
                    continue

                # Фильтр 2: Активная сессия (10:00 - 23:00 МСК)
                if not is_active_session(signal_time):
                    continue

                filtered_signals.append(det)

        print(f"\n Всего найдено сырых сигналов: {len(all_signals)}")
        print(f"🎯 Сигналов после фильтрации (Тренд + Сессия): {len(filtered_signals)}")

        # 5. Запускаем бэктестер с ATR-based SL/TP
        if filtered_signals:
            print("⚙️ Запуск бэктестинга с ATR-based SL/TP...")
            backtester = Backtester(
                initial_balance=10000.0,
                lot_size=0.01,
                atr_sl_multiplier=1.5,  # SL = 1.5 * ATR
                atr_tp_multiplier=3.0   # TP = 3.0 * ATR (R:R 1:2)
            )
            stats = backtester.run(df, connector, filtered_signals)

            print("\n" + "="*50)
            print(" 💰 РЕЗУЛЬТАТЫ БЭКТЕСТА (ATR-BASED)")
            print("="*50)
            print(f"Всего сделок: {stats['total_trades']}")
            print(f"Прибыльных (TP): {stats['wins']}")
            print(f"Убыточных (SL): {stats['losses']}")
            print(f"Нейтральных (таймаут): {stats['neutrals']}")
            print(f"Винрейт: {stats['win_rate']}")
            print(f"Чистый профит: {stats['total_pnl_rub']:.2f} RUB")
            print(f"Средний PnL на сделку: {stats['avg_pnl_per_trade']:.2f} RUB")
            print(f"Итоговый баланс: {stats['final_balance']:.2f} RUB")
            print("="*50)
        else:
            print("⚠️ После фильтрации не осталось ни одного сигнала.")

        connector.disconnect()
        print("👋 Тест завершен.")
    else:
        print("❌ Ошибка подключения к MT5.")


if __name__ == "__main__":
    main()
