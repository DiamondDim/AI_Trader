"""Safe MT5 connectivity smoke test for AI Trader."""

import os

import config
from broker.mt5_connector import get_mt5_connector


def main() -> int:
    print("🚀 Запуск AI_Trader...")
    connector = get_mt5_connector()

    if config.DEMO_MODE:
        print("🛡️ DEMO_MODE: торговые операции разрешены только через защищённый connector API.")
    else:
        print("🚨 DEMO_MODE выключен. В этом smoke-test торговый ордер всё равно не отправляется.")

    print("🔄 Подключение к MT5...")
    if not connector.connect(interactive=True):
        print("❌ Не удалось подключиться к MT5. Проверь mt5_credentials.py / переменные окружения и запущенный терминал.")
        return 1

    try:
        account_info = connector.get_account_info()
        if account_info:
            print(f"💰 Баланс: {account_info['balance']} {account_info['currency']}")
            print(f"📈 Эквити: {account_info['equity']} {account_info['currency']}")
            print(f"🏢 Брокер: {account_info['company']}")

        symbol = config.SYMBOL
        price = connector.get_current_price(symbol)
        if price:
            print(f"📊 {symbol}: Bid={price['bid']}, Ask={price['ask']}")
        else:
            print(f"⚠️ Не удалось получить цену {symbol}. Проверь символ в Обзоре рынка MT5.")

        # По умолчанию main.py ничего не торгует. Старый ручной smoke-test
        # можно явно включить переменной окружения.
        if os.getenv("AI_TRADER_RUN_ORDER_TEST", "false").lower() in {"1", "true", "yes", "on"}:
            if not price:
                print("⚠️ Order-test пропущен: нет текущей цены.")
            elif not config.DEMO_MODE:
                print("🛑 Order-test заблокирован: DEMO_MODE выключен.")
            else:
                print("🧪 Выполняется явный DEMO order-test...")
                spread = max(price['ask'] - price['bid'], 0.0)
                sl_distance = max(spread * 5.0, 0.0050)
                tp_distance = sl_distance * 2.0
                ticket = connector.place_order(
                    symbol=symbol,
                    order_type=__import__('MetaTrader5').ORDER_TYPE_BUY,
                    volume=0.01,
                    sl=price['ask'] - sl_distance,
                    tp=price['ask'] + tp_distance,
                    comment="AI_Trader_Demo_OrderTest",
                )
                print(f"🎫 Результат order-test: {ticket if ticket else 'ордер не открыт'}")
        else:
            print("ℹ️ Order-test не выполнялся. Для явного теста задайте AI_TRADER_RUN_ORDER_TEST=true.")
        return 0
    finally:
        connector.disconnect()
        print("👋 Завершение работы.")


if __name__ == "__main__":
    raise SystemExit(main())
