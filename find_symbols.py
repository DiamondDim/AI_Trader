import MetaTrader5 as mt5
import config

print("🔍 Сканируем доступные символы в терминале...")

if not mt5.initialize():
    print("❌ Ошибка инициализации MT5")
else:
    if not mt5.login(config.MT5_LOGIN, config.MT5_PASSWORD, config.MT5_SERVER):
        print("❌ Ошибка логина")
    else:
        symbols = mt5.symbols_get()
        # Ищем все символы, содержащие EURUSD
        eur_symbols = [s.name for s in symbols if 'EURUSD' in s.name.upper()]

        print(f"\n✅ Найдено символов с EURUSD: {len(eur_symbols)}")
        for s in eur_symbols:
            print(f"   - {s}")

        # Если вдруг не нашли EURUSD, покажем первые 15 любых символов для примера
        if not eur_symbols:
            print("\n️ Точное совпадение 'EURUSD' не найдено. Вот первые 15 доступных символов:")
            for s in symbols[:15]:
                print(f"   - {s.name}")

    mt5.shutdown()
