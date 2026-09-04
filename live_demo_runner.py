"""Controlled live/demo EMA Pullback runner using the shared MT5 connector."""

import time
import logging
from datetime import datetime
from typing import Dict, Any, Optional

import MetaTrader5 as mt5
import pandas as pd

import config
from broker.mt5_connector import get_mt5_connector
from core.risk import RiskCalculator
from strategy_intraday.ema_pullback import generate_ema_pullback_signals
from utils.helpers import is_active_session
from utils.market_checker import get_market_checker

TRADING_CONFIG = [{"symbol": "GBPUSDrfd", "timeframe": "M15", "sl_mult": 1.8, "tp_mult": 2.0, "bars_to_load": 200}]
RISK_PER_TRADE = 0.015
CHECK_INTERVAL = 60
MAGIC_NUMBER = 20260829


def setup_logger() -> logging.Logger:
    logger = logging.getLogger("LiveTrader")
    logger.setLevel(logging.INFO)
    if logger.handlers: return logger
    formatter = logging.Formatter("%(asctime)s | %(levelname)-8s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    handler = logging.FileHandler(f"logs/live_trader_{datetime.now().strftime('%Y%m%d')}.log", encoding="utf-8")
    handler.setFormatter(formatter); logger.addHandler(handler)
    console = logging.StreamHandler(); console.setFormatter(formatter); logger.addHandler(console)
    return logger


logger = setup_logger()


def get_initial_balance(connector=None) -> float:
    connector = connector or get_mt5_connector()
    info = connector.get_account_info()
    return float(info["balance"]) if info else 0.0


def has_open_position(symbol: str) -> bool:
    positions = mt5.positions_get(symbol=symbol)
    return bool(positions and any(pos.magic == MAGIC_NUMBER for pos in positions))


def calculate_dynamic_lot(entry_price: float, sl_price: float, symbol_info: dict,
                          balance: float, risk_per_trade: float) -> Optional[float]:
    return RiskCalculator.lot_size(balance, risk_per_trade, entry_price, sl_price, symbol_info)


def is_new_candle_closed(connector, symbol: str, timeframe: str, last_candle_time: dict) -> bool:
    rates = connector.get_rates(symbol, timeframe, 2)
    if len(rates) < 2: return False
    last_closed_time = rates.index[-2]
    if symbol not in last_candle_time:
        last_candle_time[symbol] = last_closed_time; return False
    if last_closed_time > last_candle_time[symbol]:
        last_candle_time[symbol] = last_closed_time; return True
    return False


def check_and_trade(connector, trade_config: Dict[str, Any], balance: float) -> bool:
    symbol, timeframe = trade_config["symbol"], trade_config["timeframe"]
    if not is_active_session(datetime.now()): return False
    resolved = connector.resolve_symbol(symbol)
    if not resolved or has_open_position(resolved): return False

    df = connector.get_rates(resolved, timeframe, trade_config["bars_to_load"])
    if len(df) < 100: return False
    signals = generate_ema_pullback_signals(df)
    if not signals or signals[-1]["index"] != len(df) - 2: return False

    latest = signals[-1]
    price = connector.get_current_price(resolved)
    info = connector.get_symbol_info(resolved)
    if not price or not info: return False
    order_type = mt5.ORDER_TYPE_BUY if latest["type"] == "bullish" else mt5.ORDER_TYPE_SELL
    entry_price = price["ask"] if order_type == mt5.ORDER_TYPE_BUY else price["bid"]
    atr = float(df.iloc[-2]["atr_14"])
    sl_mult, tp_mult = trade_config["sl_mult"], trade_config["tp_mult"]
    if latest["type"] == "bullish":
        sl_price, tp_price = entry_price - atr * sl_mult, entry_price + atr * tp_mult
        direction = "LONG"
    else:
        sl_price, tp_price = entry_price + atr * sl_mult, entry_price - atr * tp_mult
        direction = "SHORT"

    lot = calculate_dynamic_lot(entry_price, sl_price, info, balance, RISK_PER_TRADE)
    if lot is None: return False
    logger.info(f"🎯 СИГНАЛ: {resolved} {direction} | Цена={entry_price:.5f} | SL={sl_price:.5f} | TP={tp_price:.5f} | Лот={lot}")
    ticket = connector.place_order(resolved, order_type, lot, sl_price, tp_price,
                                   comment=f"EMA_Pullback_{direction}", magic_number=MAGIC_NUMBER)
    return bool(ticket)


def run() -> None:
    logger.info("=" * 70)
    logger.info("🚀 ЗАПУСК LIVE DEMO TRADER")
    logger.info(f"Риск на сделку: {RISK_PER_TRADE * 100:.2f}%")
    logger.info("Торговое окно брокера: Пн-Пт 07:00-22:00 МСК")
    logger.info("=" * 70)
    if not config.DEMO_MODE:
        logger.critical("DEMO_MODE=False: live runner остановлен защитой.")
        return

    connector = get_mt5_connector()
    if not connector.connect(interactive=True):
        logger.critical("Не удалось подключиться к MT5"); return
    try:
        checker = get_market_checker()
        last_candle_time: Dict[str, Any] = {}
        while True:
            for trade_config in TRADING_CONFIG:
                symbol = trade_config["symbol"]
                try:
                    if not is_new_candle_closed(connector, symbol, trade_config["timeframe"], last_candle_time): continue
                    ok, reason = checker.check(symbol)
                    if not ok:
                        logger.info(f"⏸️ {symbol}: {reason}"); continue
                    check_and_trade(connector, trade_config, get_initial_balance(connector))
                except Exception as exc:
                    logger.exception(f"Ошибка обработки {symbol}: {exc}")
            time.sleep(CHECK_INTERVAL)
    except KeyboardInterrupt:
        logger.info("Остановка пользователем")
    finally:
        connector.disconnect()


if __name__ == "__main__":
    run()
