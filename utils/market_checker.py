"""Lightweight market pre-trade checks used by live runners."""

from typing import Tuple

import MetaTrader5 as mt5

from broker.mt5_connector import get_mt5_connector


class MarketChecker:
    def __init__(self):
        self.connector = get_mt5_connector()

    def check(self, symbol: str) -> Tuple[bool, str]:
        if not self.connector._ensure_connected():
            return False, "MT5 is not connected"
        resolved = self.connector.resolve_symbol(symbol)
        if not resolved:
            return False, f"symbol not found: {symbol}"
        info = mt5.symbol_info(resolved)
        tick = mt5.symbol_info_tick(resolved)
        if info is None or tick is None:
            return False, f"market data unavailable: {resolved}"
        if not getattr(info, "visible", True):
            mt5.symbol_select(resolved, True)
        if getattr(info, "trade_mode", 0) == getattr(mt5, "SYMBOL_TRADE_MODE_DISABLED", -1):
            return False, f"trading disabled: {resolved}"
        if tick.bid <= 0 or tick.ask <= 0:
            return False, f"invalid tick: {resolved}"
        if tick.ask < tick.bid:
            return False, f"invalid spread: {resolved}"
        return True, "market data OK"


def get_market_checker() -> MarketChecker:
    return MarketChecker()
