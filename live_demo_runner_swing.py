"""
live_demo_runner_swing.py
Демо-бот для Swing-стратегии на H1.
Торгует только на проверенных связках с PF > 1.3.
"""
import time
import sys
import os
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import MetaTrader5 as mt5
import config
from broker.mt5_connector import get_mt5_connector
from core.indicators import Indicators
from core.risk import RiskCalculator

# Попытка импорта swing-стратегии (имя функции уточни в strategy_swing)
try:
    from strategy_swing import generate_swing_signals
except ImportError:
    try:
        from strategy_swing import analyze_swing_signals as generate_swing_signals
    except ImportError:
        print("[!] Не удалось импортировать swing-стратегию. Проверь strategy_swing/")
        sys.exit(1)

# ============================================================================
# КОНФИГУРАЦИЯ
# ============================================================================

# Whitelist из 8 лучших связок (все H1, PF > 1.3)
TRADING_CONFIG = [
    {'symbol': 'EURUSDrfd',  'sl_mult': 1.5, 'tp_mult': 3.0},
    {'symbol': 'USDDKKrfd',  'sl_mult': 1.5, 'tp_mult': 3.0},
    {'symbol': 'EURJPYrfd',  'sl_mult': 1.5, 'tp_mult': 3.0},
    {'symbol': 'USDNOKrfd',  'sl_mult': 1.5, 'tp_mult': 3.0},
    {'symbol': 'AUDJPYrfd',  'sl_mult': 1.5, 'tp_mult': 3.0},
    {'symbol': 'AUDNZDrfd',  'sl_mult': 1.5, 'tp_mult': 3.0},
    {'symbol': 'EURGBPrfd',  'sl_mult': 1.5, 'tp_mult': 3.0},
    {'symbol': 'USDCADrfd',  'sl_mult': 1.5, 'tp_mult': 3.0},
]

RISK_PER_TRADE = 0.015   # 1.5% риска на сделку
CHECK_INTERVAL = 60      # Проверка каждую минуту
MAGIC_NUMBER = 20260902  # Уникальный ID для наших ордеров
TIMEFRAME = 'H1'         # Swing торгуем только на H1
BARS_TO_LOAD = 200       # Достаточно для индикаторов

# ============================================================================
# ЛОГИРОВАНИЕ
# ============================================================================

def setup_logger() -> logging.Logger:
    logger = logging.getLogger('SwingTrader')
    logger.setLevel(logging.INFO)

    formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    if not os.path.exists('logs'):
        os.makedirs('logs')

    file_handler = logging.FileHandler(
        f'logs/swing_trader_{datetime.now().strftime("%Y%m%d")}.log',
        encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logger

logger = setup_logger()

# ============================================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================================================

def is_market_open(symbol: str) -> bool:
    """Проверяет, открыт ли рынок для символа (защита от выходных)."""
    tick = mt5.symbol_info_tick(symbol)
    if tick is None or tick.bid <= 0 or tick.ask <= 0:
        return False

    symbol_info = mt5.symbol_info(symbol)
    if symbol_info is None or symbol_info.trade_mode != 0:
        return False

    return True


def has_open_position(symbol: str) -> bool:
    """Проверяет, есть ли уже открытая позиция по символу с нашим MAGIC_NUMBER."""
    positions = mt5.positions_get(symbol=symbol)
    if positions is None:
        return False
    return any(pos.magic == MAGIC_NUMBER for pos in positions)


def get_last_closed_bar_time(symbol: str) -> Optional[datetime]:
    """Возвращает время последней ЗАКРЫТОЙ свечи."""
    rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H1, 0, 2)
    if rates is None or len(rates) < 2:
        return None
    return datetime.fromtimestamp(rates[-2]['time'])


def calculate_lot(entry_price: float, sl_price: float, symbol_info: dict) -> Optional[float]:
    """Рассчитывает лот через централизованный RiskCalculator."""
    account_info = mt5.account_info()
    if account_info is None:
        logger.error("Не удалось получить информацию о счете")
        return None

    has_tick_value = bool(symbol_info.get('trade_tick_value')) and bool(symbol_info.get('trade_tick_size'))
    conversion_rate = 1.0 if has_tick_value else 90.0

    lot = RiskCalculator.lot_size(
        balance=account_info.balance,
        risk_per_trade=RISK_PER_TRADE,
        entry_price=entry_price,
        sl_price=sl_price,
        symbol_info=symbol_info,
        conversion_rate=conversion_rate,
    )

    volume_min = symbol_info.get('volume_min', 0.01)
    if lot is None or lot < volume_min:
        logger.warning(f"⚠️ Лот слишком мал для {symbol} (lot={lot}, min={volume_min})")
        return None

    return round(lot, 2)


def load_dataframe(symbol: str) -> Optional[Any]:
    """Загружает данные в DataFrame с индикаторами."""
    import pandas as pd
    rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H1, 0, BARS_TO_LOAD)
    if rates is None or len(rates) < 100:
        return None

    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    df.set_index('time', inplace=True)
    df.columns = [col.lower() for col in df.columns]

    # Добавляем индикаторы
    df = Indicators().add_all(df, include_ema_200=True)
    return df


# ============================================================================
# ГЛАВНАЯ ЛОГИКА
# ============================================================================

def check_and_trade(trade_config: Dict[str, Any]) -> bool:
    """Проверяет условия и открывает сделку."""
    symbol = trade_config['symbol']
    sl_mult = trade_config['sl_mult']
    tp_mult = trade_config['tp_mult']

    if not is_market_open(symbol):
        return False

    if has_open_position(symbol):
        return False

    df = load_dataframe(symbol)
    if df is None or df.empty:
        logger.warning(f"Не удалось загрузить данные для {symbol}")
        return False

    # Генерируем сигналы
    signals = generate_swing_signals(df)
    if not signals:
        return False

    # Берём самый свежий сигнал
    latest_signal = signals[-1]

    # Проверяем, что сигнал на последней ЗАКРЫТОЙ свече
    last_closed_idx = len(df) - 2
    if latest_signal['index'] != last_closed_idx:
        return False

    signal_type = latest_signal.get('type', 'bullish')

    # Рассчитываем SL/TP по ATR
    entry_price = float(df.iloc[-1]['close'])
    atr = float(df.iloc[-1].get('atr_14', 0.0))
    if atr <= 0:
        logger.warning(f"ATR невалиден для {symbol}")
        return False

    if signal_type == 'bullish':
        sl_price = entry_price - (atr * sl_mult)
        tp_price = entry_price + (atr * tp_mult)
        order_type = mt5.ORDER_TYPE_BUY
        direction = 'LONG'
    else:
        sl_price = entry_price + (atr * sl_mult)
        tp_price = entry_price - (atr * tp_mult)
        order_type = mt5.ORDER_TYPE_SELL
        direction = 'SHORT'

    # Рассчитываем лот
    symbol_info = mt5.symbol_info(symbol)._asdict()
    lot = calculate_lot(entry_price, sl_price, symbol_info)
    if lot is None:
        return False

    logger.info(
        f"🎯 СИГНАЛ: {symbol} {direction} | "
        f"Цена: {entry_price:.5f} | SL: {sl_price:.5f} | TP: {tp_price:.5f} | Лот: {lot}"
    )

    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        return False

    price = tick.ask if order_type == mt5.ORDER_TYPE_BUY else tick.bid

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": lot,
        "type": order_type,
        "price": price,
        "sl": sl_price,
        "tp": tp_price,
        "deviation": 20,
        "magic": MAGIC_NUMBER,
        "comment": f"Swing_{symbol}",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }

    result = mt5.order_send(request)
    if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
        logger.error(
            f"❌ Ошибка ордера {symbol}: "
            f"{getattr(result, 'retcode', 'None')} - {getattr(result, 'comment', '')}"
        )
        return False

    logger.info(f"✅ ОРДЕР ОТКРЫТ! Тикет: {result.order} | Цена: {price:.5f} | Объём: {lot}")
    return True


# ============================================================================
# ГЛАВНЫЙ ЦИКЛ
# ============================================================================

def run():
    logger.info("=" * 70)
    logger.info("🚀 ЗАПУСК SWING DEMO TRADER")
    logger.info(f"Риск на сделку: {RISK_PER_TRADE * 100:.2f}%")
    logger.info(f"Таймфрейм: {TIMEFRAME}")
    logger.info(f"Пар в whitelist: {len(TRADING_CONFIG)}")
    logger.info(f"Пары: {[c['symbol'] for c in TRADING_CONFIG]}")
    logger.info("=" * 70)

    # КРИТИЧЕСКАЯ ПРОВЕРКА: только демо-режим
    if not getattr(config, 'DEMO_MODE', False):
        logger.critical("🚨 КРИТИЧЕСКАЯ ОШИБКА: DEMO_MODE = False! Торговля заблокирована.")
        return

    if not mt5.initialize():
        logger.critical(f"Ошибка инициализации MT5: {mt5.last_error()}")
        return

    if not mt5.login(config.MT5_LOGIN, config.MT5_PASSWORD, config.MT5_SERVER):
        logger.critical(f"Ошибка логина: {mt5.last_error()}")
        mt5.shutdown()
        return

    logger.info(f"✅ Подключено к MT5 (Login: {config.MT5_LOGIN}, Server: {config.MT5_SERVER})")

    account_info = mt5.account_info()
    if account_info is None:
        logger.critical("Не удалось получить баланс счёта")
        mt5.shutdown()
        return

    logger.info(f"💰 Баланс счёта: {account_info.balance:.2f} {account_info.currency}")

    # Словарь времени последней обработанной свечи для каждой пары
    last_processed_bar = {cfg['symbol']: None for cfg in TRADING_CONFIG}
    market_was_closed = False

    try:
        logger.info("🔄 Запуск основного цикла...")
        while True:
            try:
                # Проверяем рынок по первому символу
                primary_symbol = TRADING_CONFIG[0]['symbol']
                if not is_market_open(primary_symbol):
                    if not market_was_closed:
                        logger.info("⏸️ Рынок закрыт. Ожидание следующей сессии...")
                        market_was_closed = True
                    time.sleep(300)  # Проверка раз в 5 минут в выходные
                    continue

                if market_was_closed:
                    logger.info("▶️ Рынок открыт! Возобновляем торговлю.")
                    market_was_closed = False

                for trade_config in TRADING_CONFIG:
                    symbol = trade_config['symbol']

                    # Проверяем, закрылась ли новая H1 свеча
                    last_closed = get_last_closed_bar_time(symbol)
                    if last_closed is None:
                        continue

                    if last_processed_bar[symbol] is None:
                        last_processed_bar[symbol] = last_closed
                        continue

                    if last_closed > last_processed_bar[symbol]:
                        last_processed_bar[symbol] = last_closed
                        logger.info(f"🔍 Проверка {symbol} (новая H1 свеча: {last_closed})")
                        check_and_trade(trade_config)

            except Exception as e:
                logger.error(f"Ошибка в цикле: {e}", exc_info=True)

            time.sleep(CHECK_INTERVAL)

    except KeyboardInterrupt:
        logger.info("⏹️ Получен сигнал остановки (Ctrl+C)")
    finally:
        mt5.shutdown()
        logger.info("👋 Робот остановлен. MT5 отключён.")


if __name__ == "__main__":
    run()
