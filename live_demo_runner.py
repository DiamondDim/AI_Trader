"""
live_demo_runner.py
Автоматический торговый робот на основе стратегии EMA Pullback.
Работает на демо-счёте в реальном времени.

ВАЖНО: Перед запуском убедитесь, что в config.py установлено DEMO_MODE = True
"""

import time
import pandas as pd
import MetaTrader5 as mt5
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
import logging
import os

from broker.mt5_connector import get_mt5_connector
from strategy_intraday.ema_pullback import (
    generate_ema_pullback_signals,
    is_active_session,
    _ensure_indicators
)
from utils.market_checker import get_market_checker
import config

# ============================================================================
# КОНФИГУРАЦИЯ ТОРГОВЛИ
# ============================================================================

# Список инструментов для торговли с индивидуальными параметрами
# Формат: {symbol, timeframe, sl_mult, tp_mult, bars_to_load}
TRADING_CONFIG = [
    {
        'symbol': 'GBPUSDrfd',
        'timeframe': 'M15',
        'sl_mult': 1.8,  # Оптимизировано на истории
        'tp_mult': 2.0,  # Оптимизировано на истории
        'bars_to_load': 200,  # Достаточно для расчёта EMA(50) + индикаторов
    },
    # Раскомментируй после успешного теста первой пары
    # {
    #     'symbol': 'EURUSDrfd',
    #     'timeframe': 'H1',
    #     'sl_mult': 1.5,
    #     'tp_mult': 3.0,
    #     'bars_to_load': 200,
    # },
]

# Риск на сделку (1.5% — золотая середина по нашим тестам)
RISK_PER_TRADE = 0.015

# Интервал проверки (в секундах)
# Проверяем каждую минуту, торгуем только на закрытии свечи
CHECK_INTERVAL = 60

# Магический номер для идентификации наших ордеров
MAGIC_NUMBER = 20260829


# ============================================================================
# ЛОГИРОВАНИЕ
# ============================================================================

def setup_logger() -> logging.Logger:
    """Настраивает логирование в файл и консоль"""
    logger = logging.getLogger('LiveTrader')
    logger.setLevel(logging.INFO)

    # Формат логов
    formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Файловый обработчик
    if not os.path.exists('logs'):
        os.makedirs('logs')
    file_handler = logging.FileHandler(
        f'logs/live_trader_{datetime.now().strftime("%Y%m%d")}.log',
        encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Консольный обработчик
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logger


logger = setup_logger()


# ============================================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================================================

def get_initial_balance() -> float:
    """Получает текущий баланс счёта"""
    account_info = mt5.account_info()
    if account_info is None:
        logger.error(f"Не удалось получить информацию о счёте: {mt5.last_error()}")
        return 0.0
    return account_info.balance


def has_open_position(symbol: str) -> bool:
    """Проверяет, есть ли уже открытая позиция по символу"""
    positions = mt5.positions_get(symbol=symbol)
    if positions is None:
        return False
    # Фильтруем только наши позиции (по magic number)
    for pos in positions:
        if pos.magic == MAGIC_NUMBER:
            return True
    return False


def calculate_dynamic_lot(
        entry_price: float,
        sl_price: float,
        symbol_info: dict,
        balance: float,
        risk_per_trade: float
) -> Optional[float]:
    """
    Рассчитывает динамический лот на основе риска от баланса.
    Формула: lot = (balance × risk%) / (sl_distance_points × point_value_rub)
    """
    volume_min = symbol_info.get('volume_min', 0.01)
    volume_max = symbol_info.get('volume_max', 100.0)
    volume_step = symbol_info.get('volume_step', 0.01)

    # Риск в рублях
    risk_rub = balance * risk_per_trade

    # Расстояние до SL
    sl_distance = abs(entry_price - sl_price)
    if sl_distance == 0:
        logger.warning("SL совпадает с ценой входа")
        return None

    # Стоимость пункта в рублях для 1 лота
    point = symbol_info.get('point', 0.0001)
    contract_size = symbol_info.get('trade_contract_size', 100000)
    symbol_name = symbol_info.get('name', '')

    # Курс конвертации (упрощённая версия)
    if symbol_name.startswith('USD'):
        rate = 90.0
    elif symbol_name.endswith('USD'):
        base_rates = {
            'EUR': 98.0, 'GBP': 115.0, 'AUD': 60.0, 'NZD': 55.0,
            'CHF': 100.0, 'CAD': 67.0, 'JPY': 0.60,
        }
        base_curr = symbol_name[:3]
        rate = base_rates.get(base_curr, 90.0)
    elif 'RUB' in symbol_name:
        rate = 1.0
    else:
        rate = 90.0

    point_value_rub = point * contract_size * rate
    if point_value_rub == 0:
        logger.error("Не удалось рассчитать стоимость пункта")
        return None

    sl_distance_points = sl_distance / point
    lot = risk_rub / (sl_distance_points * point_value_rub)

    # Округление до шага
    lot = round(lot / volume_step) * volume_step

    # Проверка минимального лота
    if lot < volume_min:
        min_required = (volume_min * sl_distance_points * point_value_rub) / risk_per_trade
        logger.warning(
            f"⚠️ Лот {lot:.4f} < минимального {volume_min}. "
            f"Требуется депозит: {min_required:,.0f} RUB"
        )
        return None

    # Ограничение максимумом
    lot = min(lot, volume_max)
    lot = round(lot, 2)

    return lot


def is_new_candle_closed(symbol: str, timeframe: str, last_candle_time: dict) -> bool:
    """
    Проверяет, закрылась ли новая свеча.
    last_candle_time — словарь {symbol: last_closed_time}
    """
    rates = mt5.copy_rates_from_pos(symbol, _get_mt5_timeframe(timeframe), 0, 2)
    if rates is None or len(rates) < 2:
        return False

    # Последняя закрытая свеча — это rates[-2] (rates[-1] — текущая формирующаяся)
    last_closed_time = pd.to_datetime(rates[-2]['time'], unit='s')

    if symbol not in last_candle_time:
        last_candle_time[symbol] = last_closed_time
        return False

    if last_closed_time > last_candle_time[symbol]:
        last_candle_time[symbol] = last_closed_time
        return True

    return False


def _get_mt5_timeframe(tf_str: str):
    """Конвертирует строку таймфрейма в константу MT5"""
    mapping = {
        'M1': mt5.TIMEFRAME_M1,
        'M5': mt5.TIMEFRAME_M5,
        'M15': mt5.TIMEFRAME_M15,
        'M30': mt5.TIMEFRAME_M30,
        'H1': mt5.TIMEFRAME_H1,
        'H4': mt5.TIMEFRAME_H4,
        'D1': mt5.TIMEFRAME_D1,
    }
    return mapping.get(tf_str.upper())


# ============================================================================
# ГЛАВНАЯ ЛОГИКА ТОРГОВЛИ
# ============================================================================

def check_and_trade(trade_config: Dict[str, Any], balance: float) -> bool:
    """
    Проверяет условия входа и открывает сделку, если всё совпало.
    Возвращает True, если сделка была открыта.
    """
    symbol = trade_config['symbol']
    timeframe = trade_config['timeframe']
    sl_mult = trade_config['sl_mult']
    tp_mult = trade_config['tp_mult']
    bars = trade_config['bars_to_load']

    # === ПРОВЕРКА 1: Активная сессия ===
    server_time = datetime.now()  # В реальном боте лучше брать время сервера MT5
    if not is_active_session(server_time):
        return False

    # === ПРОВЕРКА 2: Нет открытой позиции ===
    if has_open_position(symbol):
        return False

    # === ЗАГРУЗКА ДАННЫХ ===
    mt5_tf = _get_mt5_timeframe(timeframe)
    rates = mt5.copy_rates_from_pos(symbol, mt5_tf, 0, bars)
    if rates is None or len(rates) < 100:
        logger.warning(f"Недостаточно данных для {symbol}")
        return False

    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    df.set_index('time', inplace=True)
    df.columns = [col.lower() for col in df.columns]

    # === РАСЧЁТ ИНДИКАТОРОВ ===
    df = _ensure_indicators(df)

    # === ГЕНЕРАЦИЯ СИГНАЛА НА ПОСЛЕДНЕЙ ЗАКРЫТОЙ СВЕЧЕ ===
    # Берём только последнюю закрытую свечу (предпоследнюю в df, т.к. последняя — формирующаяся)
    signals = generate_ema_pullback_signals(df)

    if not signals:
        return False

    # Берём самый свежий сигнал
    latest_signal = signals[-1]

    # Проверяем, что сигнал на последней закрытой свече
    last_closed_idx = len(df) - 2  # -1 это текущая формирующаяся
    if latest_signal['index'] != last_closed_idx:
        return False

    # === РАСЧЁТ SL/TP ===
    entry_price = df.iloc[-1]['close']  # Входим по текущей цене
    atr = df.iloc[-1]['atr_14']

    if latest_signal['type'] == 'bullish':
        sl_price = entry_price - (atr * sl_mult)
        tp_price = entry_price + (atr * tp_mult)
        order_type = mt5.ORDER_TYPE_BUY
        direction = 'LONG'
    else:
        sl_price = entry_price + (atr * sl_mult)
        tp_price = entry_price - (atr * tp_mult)
        order_type = mt5.ORDER_TYPE_SELL
        direction = 'SHORT'

    # === РАСЧЁТ ЛОТА ===
    symbol_info = mt5.symbol_info(symbol)._asdict()
    lot = calculate_dynamic_lot(entry_price, sl_price, symbol_info, balance, RISK_PER_TRADE)

    if lot is None:
        logger.warning(f"Не удалось рассчитать лот для {symbol}")
        return False

    # === ОТКРЫТИЕ ОРДЕРА ===
    logger.info(
        f"🎯 СИГНАЛ: {symbol} {direction} | "
        f"Цена: {entry_price:.5f} | SL: {sl_price:.5f} | TP: {tp_price:.5f} | "
        f"Лот: {lot} | ATR: {atr:.5f}"
    )

    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        logger.error(f"Не удалось получить тик для {symbol}")
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
        "comment": f"EMA_Pullback_{direction}",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }

    result = mt5.order_send(request)

    if result.retcode != mt5.TRADE_RETCODE_DONE:
        logger.error(
            f"❌ Ошибка открытия ордера: {result.retcode} - {result.comment}"
        )
        return False

    logger.info(
        f"✅ ОРДЕР ОТКРЫТ! Тикет: {result.order} | "
        f"Цена: {price:.5f} | Объём: {lot}"
    )
    return True


# ============================================================================
# ГЛАВНЫЙ ЦИКЛ
# ============================================================================

def run():
    """Главный цикл торгового робота с проверкой рынка"""
    logger.info("=" * 70)
    logger.info("🚀 ЗАПУСК LIVE DEMO TRADER")
    logger.info(f"Стратегия: EMA Pullback")
    logger.info(f"Риск на сделку: {RISK_PER_TRADE * 100:.2f}%")
    logger.info(f"Инструменты: {[c['symbol'] for c in TRADING_CONFIG]}")
    logger.info(f"Интервал проверки: {CHECK_INTERVAL} сек")
    logger.info("=" * 70)

    # === ЖЁСТКАЯ ПРОВЕРКА DEMO-РЕЖИМА ===
    if not config.DEMO_MODE:
        logger.critical(
            "🚨 КРИТИЧЕСКАЯ ОШИБКА: DEMO_MODE = False! "
            "Торговля на реальном счёте заблокирована."
        )
        return

    # === ПОДКЛЮЧЕНИЕ К MT5 ===
    if not mt5.initialize():
        logger.critical(f"Ошибка инициализации MT5: {mt5.last_error()}")
        return

    if not mt5.login(config.MT5_LOGIN, config.MT5_PASSWORD, config.MT5_SERVER):
        logger.critical(f"Ошибка логина: {mt5.last_error()}")
        mt5.shutdown()
        return

    logger.info(f"✅ Подключено к MT5 (Login: {config.MT5_LOGIN}, Server: {config.MT5_SERVER})")

    balance = get_initial_balance()
    if balance <= 0:
        logger.critical("Не удалось получить баланс счёта")
        mt5.shutdown()
        return

    logger.info(f"💰 Баланс счёта: {balance:.2f} {mt5.account_info().currency}")

    # Инициализируем MarketChecker
    market_checker = get_market_checker()
    last_candle_time = {}
    market_was_closed = False  # Флаг, чтобы не спамить логами

    try:
        logger.info("🔄 Запуск основного цикла...")

        while True:
            try:
                current_time = datetime.now()

                # === ПРОВЕРКА ДОСТУПНОСТИ РЫНКА ===
                # Проверяем первый символ из конфига (обычно все открываются одновременно)
                primary_symbol = TRADING_CONFIG[0]['symbol']
                is_allowed, reason = market_checker.is_trading_allowed(
                    primary_symbol, current_time
                )

                if not is_allowed:
                    # Логируем только один раз при переходе в состояние "закрыт"
                    if not market_was_closed:
                        logger.info(f"⏸️ Рынок закрыт: {reason}")
                        next_session = market_checker.get_next_trading_session(current_time)
                        logger.info(f"📅 Следующая сессия: {next_session.strftime('%Y-%m-%d %H:%M МСК')}")
                        market_was_closed = True

                    # В выходные/праздники проверяем реже (раз в 5 минут)
                    time.sleep(300)
                    continue

                # Рынок открыт — сбрасываем флаг
                if market_was_closed:
                    logger.info(f"▶️ Рынок открыт! Возобновляем торговлю.")
                    market_was_closed = False

                # Обновляем баланс перед каждой итерацией
                balance = get_initial_balance()

                for trade_config in TRADING_CONFIG:
                    symbol = trade_config['symbol']
                    timeframe = trade_config['timeframe']

                    # Проверяем, закрылась ли новая свеча
                    if not is_new_candle_closed(symbol, timeframe, last_candle_time):
                        continue

                    # Дополнительная проверка для конкретного символа
                    if not market_checker.is_market_open_for_symbol(symbol):
                        logger.warning(f"⚠️ {symbol}: рынок закрыт, пропускаем")
                        continue

                    logger.info(f"🔍 Проверка {symbol} ({timeframe})...")

                    # Проверяем условия и торгуем
                    check_and_trade(trade_config, balance)

            except Exception as e:
                logger.error(f"Ошибка в цикле проверки: {e}", exc_info=True)

            # Ждём следующую итерацию
            time.sleep(CHECK_INTERVAL)

    except KeyboardInterrupt:
        logger.info("⏹️ Получен сигнал остановки (Ctrl+C)")
    finally:
        mt5.shutdown()
        logger.info("👋 Робот остановлен. MT5 отключён.")


if __name__ == "__main__":
    run()
