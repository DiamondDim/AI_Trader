import config
from broker.mt5_connector import get_mt5_connector
import MetaTrader5 as mt5_lib


def main():
    print("🚀 Запуск AI_Trader...")

    # Получаем экземпляр коннектора
    connector = get_mt5_connector()

    # Проверяем режим (важно для безопасности!)
    if config.DEMO_MODE:
        print("🛡️ ВНИМАНИЕ: Активирован БЕЗОПАСНЫЙ ДЕМО-РЕЖИМ. Реальные сделки запрещены.")
    else:
        print("🚨 ВНИМАНИЕ: Активирован РЕАЛЬНЫЙ режим торговли! Будь предельно осторожен!")

    # Подключаемся к MT5
    print(f"🔄 Подключение к MT5 (Сервер: {config.MT5_SERVER})...")
    if connector.connect():
        print("✅ Успешное подключение к терминалу!")

        # Получаем информацию о счете
        account_info = connector.get_account_info()
        if account_info:
            print(f"💰 Баланс: {account_info['balance']} {account_info['currency']}")
            print(f"📈 Эквити (средства): {account_info['equity']} {account_info['currency']}")
            print(f"🏢 Брокер: {account_info['company']}")

        # Тестовая проверка цены по символу из конфига
        symbol = config.SYMBOL
        price = connector.get_current_price(symbol)
        if price:
            print(f"📊 Текущая цена {symbol}: Bid = {price['bid']}, Ask = {price['ask']}")
        else:
            print(f"❌ Не удалось получить цену для {symbol}. Проверь, открыт ли этот символ в Обзоре рынка MT5.")

    else:
        print("❌ Ошибка подключения к MT5. Проверь логин, пароль и сервер в config.py, а также запущен ли терминал.")

    print("\n ТЕСТОВАЯ СДЕЛКА (Демо-режим)...")

    # Пытаемся открыть покупку 0.01 лота
    ticket = connector.place_order(
        symbol=config.SYMBOL,
        order_type=mt5_lib.ORDER_TYPE_BUY,
        volume=0.01,
        sl=price['bid'] - 0.0050,  # Stop Loss на 50 пунктов ниже
        tp=price['bid'] + 0.0100,  # Take Profit на 100 пунктов выше
        comment="Test_Dima_01"
    )

    if ticket:
        print(f"🎉 УРА! Ордер открыт. Тикет: {ticket}")
    else:
        print("⚠️ Ордер не открыт. Проверь логи выше.")

    # Корректно отключаемся
    connector.disconnect()
    print("👋 Завершение работы. До встречи!")


if __name__ == "__main__":
    main()
