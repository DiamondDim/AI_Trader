"""
Live EMA Pullback runner.
Keeps the original strategy/session/order flow while delegating position sizing
and symbol economics to the shared core/broker infrastructure.
"""
import time
import logging
import os
from datetime import datetime
from typing import Dict, Any, Optional

import MetaTrader5 as mt5
import pandas as pd

import config
from broker.mt5_connector import get_mt5_connector
from core.risk import RiskCalculator
from strategy_intraday.ema_pullback import (
    generate_ema_pullback_signals,
    is_active_session,
    _ensure_indicators,
)
from utils.market_checker import get_market_checker

TRADING_CONFIG = [
    {
        "symbol": "GBPUSDrfd",
        "timeframe": "M15",
        "sl_mult": 1.8,
        "tp_mult": 2.0,
        "bars_to_load": 200,
    },
]
RISK_PER_TRADE = 0.015
CHECK_INTERVAL = 60
MAGIC_NUMBER = 20260829


def setup_logger() -> logging.Logger:
    logger = logging.getLogger("LiveTrader")
    logger.setLevel(logging.INFO)
    if logger.handlers:
        return logger
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    os.makedirs("logs", exist_ok=True)
    file_handler = logging.FileHandler(
        f"logs/live_trader_{datetime.now().strftime('%Y%m%d')}.log",
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    return logger


logger = setup_logger()


def get_initial_balance() -> float:
    account_info = mt5.account_info()
    if account_info is None:
        logger.error(f"Не удалось получить информацию о счёте: {mt5.last_error()}")
        return 0.0
    return float(account_info.balance)


def has_open_position(symbol: str) -> bool:
    positions = mt5.positions_get(symbol=symbol)
    if positions is None:
        return False
    return any(pos.magic == MAGIC_NUMBER for pos in positions)


def calculate_dynamic_lot(
    entry_price: float,
    sl_price: float,
    symbol_info: dict,
    balance: float,
    risk_per_trade: float,
) -> Optional[float]:
    """Compatibility wrapper using the shared risk calculator."""
    return RiskCalculator.lot_size(
        balance=balance,
        risk_per_trade=risk_per_trade,
        entry_price=entry_price,
        sl_price=sl_price,
        symbol_info=symbol_info,
    )


def is_new_candle_closed(symbol: str, timeframe: str, last_candle_time: dict) -> bool:
    rates = mt5.copy_rates_from_pos(symbol, _get_mt5_timeframe(timeframe), 0, 2)
    if rates is None or len(rates) < 2:
        return False
    last_closed_time = pd.to_datetime(rates[-2]["time"], unit="s")
    if symbol not in last_candle_time:
        last_candle_time[symbol] = last_closed_time
        return False
    if last_closed_time > last_candle_time[symbol]:
        last_candle_time[symbol] = last_closed_time
        return True
    return False


def _get_mt5_timeframe(tf_str: str):
    mapping = {
        "M1": mt5.TIMEFRAME_M1,
        "M5": mt5.TIMEFRAME_M5,
        "M15": mt5.TIMEFRAME_M15,
        "M30": mt5.TIMEFRAME_M30,
        "H1": mt5.TIMEFRAME_H1,
        "H4": mt5.TIMEFRAME_H4,
        "D1": mt5.TIMEFRAME_D1,
    }
    return mapping.get(tf_str.upper())


def check_and_trade(trade_config: Dict[str, Any], balance: float) -> bool:
    symbol = trade_config["symbol"]
    timeframe = trade_config["timeframe"]
    sl_mult = trade_config["sl_mult"]
    tp_mult = trade_config["tp_mult"]
    bars = trade_config["bars_to_load"]

    if not is_active_session(datetime.now()):
        return False
    if has_open_position(symbol):
        return False

    mt5_tf = _get_mt5_timeframe(timeframe)
    rates = mt5.copy_rates_from_pos(symbol, mt5_tf, 0, bars)
    if rates is None or len(rates) < 100:
        logger.warning(f"Недостаточно данных для {symbol}")
        return False

    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    df.set_index("time", inplace=True)
    df.columns = [col.lower() for col in df.columns]
    df = _ensure_indicators(df)

    signals = generate_ema_pullback_signals(df)
    if not signals:
        return False

    latest_signal = signals[-1]
    last_closed_idx = len(df) - 2
    if latest_signal["index"] != last_closed_idx:
        return False

    # Preserve the original live flow: signal from the last closed candle,
    # then execute at the current market bid/ask.
    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        logger.error(f"Не удалось получить тик для {symbol}")
        return False

    order_type = (
        mt5.ORDER_TYPE_BUY
        if latest_signal["type"] == "bullish"
        else mt5.ORDER_TYPE_SELL
    )
    entry_price = tick.ask if order_type == mt5.ORDER_TYPE_BUY else tick.bid

    atr = float(df.iloc[-2]["atr_14"])
    if latest_signal["type"] == "bullish":
        sl_price = entry_price - atr * sl_mult
        tp_price = entry_price + atr * tp_mult
        direction = "LONG"
    else:
        sl_price = entry_price + atr * sl_mult
        tp_price = entry_price - atr * tp_mult
        direction = "SHORT"

    info = mt5.symbol_info(symbol)
    if info is None:
        logger.error(f"Не удалось получить информацию о символе {symbol}")
        return False

    lot = calculate_dynamic_lot(
        entry_price,
        sl_price,
        info._asdict(),
        balance,
        RISK_PER_TRADE,
    )
    if lot is None:
        logger.warning(f"Не удалось рассчитать лот для {symbol}")
        return False

    logger.info(
        f"🎯 СИГНАЛ: {symbol} {direction} | Цена: {entry_price:.5f} | "
        f"SL: {sl_price:.5f} | TP: {tp_price:.5f} | Лот: {lot} | ATR: {atr:.5f}"
    )

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": lot,
        "type": order_type,
        "price": entry_price,
        "sl": sl_price,
        "tp": tp_price,
        "deviation": 20,
        "magic": MAGIC_NUMBER,
        "comment": f"EMA_Pullback_{direction}",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }

    result = mt5.order_send(request)
    if result is None:
        logger.error(f"❌ order_send вернул None: {mt5.last_error()}")
        return False
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        logger.error(f"❌ Ошибка открытия ордера: {result.retcode} - {result.comment}")
        return False

    logger.info(
        f"✅ ОРДЕР ОТКРЫТ! Тикет: {result.order} | "
        f"Цена: {entry_price:.5f} | Объём: {lot}"
    )
    return True


def run():
    logger.info("=" * 70)
    logger.info("🚀 ЗАПУСК LIVE DEMO TRADER")
    logger.info("Стратегия: EMA Pullback")
    logger.info(f"Риск на сделку: {RISK_PER_TRADE * 100:.2f}%")
    logger.info(f"Инструменты: {[c['symbol'] for c in TRADING_CONFIG]}")
    logger.info(f"Интервал проверки: {CHECK_INTERVAL} сек")
    logger.info("=" * 70)

    if not config.DEMO_MODE:
        logger.critical(
            "🚨 КРИТИЧЕСКАЯ ОШИБКА: DEMO_MODE = False! "
            "Торговля на реальном счёте заблокирована."
        )
        return

    connector = get_mt5_connector()
    if not connector.connect():
        logger.critical("Не удалось подключиться к MT5")
        return

    try:
        balance = get_initial_balance()
        logger.info(f"💰 Баланс: {balance:,.2f}")
        market_checker = get_market_checker()
        last_candle_time: Dict[str, Any] = {}

        while True:
            for trade_config in TRADING_CONFIG:
                symbol = trade_config["symbol"]
                timeframe = trade_config["timeframe"]
                try:
                    if not is_new_candle_closed(symbol, timeframe, last_candle_time):
                        continue
                    market_ok, reason = market_checker.check(symbol)
                    if not market_ok:
                        logger.info(f"⏸️ {symbol}: {reason}")
                        continue
                    balance = get_initial_balance()
                    check_and_trade(trade_config, balance)
                except Exception as exc:
                    logger.exception(f"Ошибка обработки {symbol}: {exc}")
            time.sleep(CHECK_INTERVAL)
    except KeyboardInterrupt:
        logger.info("Остановка пользователем")
    finally:
        connector.disconnect()


if __name__ == "__main__":
    run()
