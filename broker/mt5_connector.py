"""MetaTrader 5 connector for data retrieval and trading operations."""

from datetime import datetime
from typing import Optional, Dict, Any, List

import MetaTrader5 as mt5
import pandas as pd

import config
from utils.logger import LoggingMixin


class MT5Connector(LoggingMixin):
    """Connector for MetaTrader 5 terminal."""

    def __init__(self, login: Optional[int] = None,
                 password: Optional[str] = None,
                 server: Optional[str] = None):
        super().__init__()
        self.login = login or config.MT5_LOGIN
        self.password = password or config.MT5_PASSWORD
        self.server = server or config.MT5_SERVER
        self.connected = False
        self.timeframe_map = {
            'M1': mt5.TIMEFRAME_M1, 'M5': mt5.TIMEFRAME_M5,
            'M15': mt5.TIMEFRAME_M15, 'M30': mt5.TIMEFRAME_M30,
            'H1': mt5.TIMEFRAME_H1, 'H4': mt5.TIMEFRAME_H4,
            'D1': mt5.TIMEFRAME_D1, 'W1': mt5.TIMEFRAME_W1,
            'MN1': mt5.TIMEFRAME_MN1,
        }

    def connect(self, login: Optional[int] = None,
                password: Optional[str] = None,
                server: Optional[str] = None) -> bool:
        try:
            if login is not None:
                self.login = login
            if password is not None:
                self.password = password
            if server is not None:
                self.server = server
            if not mt5.initialize():
                self.log_error(f"MT5 initialization failed: {mt5.last_error()}")
                return False
            if not mt5.login(self.login, self.password, self.server, timeout=config.MT5_TIMEOUT):
                self.log_error(f"MT5 login failed: {mt5.last_error()}")
                mt5.shutdown()
                return False
            self.connected = True
            self.log_info(f"Connected to MT5 (Login: {self.login}, Server: {self.server})")
            account_info = self.get_account_info()
            if account_info:
                self.log_info(f"Account balance: {account_info.get('balance', 0):.2f} {account_info.get('currency', 'USD')}")
            return True
        except Exception as exc:
            self.log_error(f"Error connecting to MT5: {exc}")
            return False

    def disconnect(self) -> bool:
        try:
            if self.connected:
                mt5.shutdown()
                self.connected = False
                self.log_info("Disconnected from MT5")
            return True
        except Exception as exc:
            self.log_error(f"Error disconnecting from MT5: {exc}")
            return False

    def resolve_symbol(self, symbol: str) -> Optional[str]:
        """Resolve a logical symbol to the exact broker symbol name."""
        if not self.connected:
            return None
        direct = mt5.symbol_info(symbol)
        if direct is not None:
            return direct.name
        try:
            for candidate in mt5.symbols_get() or []:
                if symbol.upper() in candidate.name.upper():
                    return candidate.name
        except Exception as exc:
            self.log_error(f"Error resolving symbol {symbol}: {exc}")
        return None

    def get_rates(self, symbol: str, timeframe: str, bars: int = 100) -> pd.DataFrame:
        if not self.connected:
            self.log_error("Not connected to MT5")
            return pd.DataFrame()
        mt5_timeframe = self.timeframe_map.get(timeframe.upper())
        if mt5_timeframe is None:
            self.log_error(f"Unsupported timeframe: {timeframe}")
            return pd.DataFrame()
        resolved = self.resolve_symbol(symbol)
        if not resolved:
            self.log_warning(f"Symbol {symbol} not found")
            return pd.DataFrame()
        try:
            rates = mt5.copy_rates_from_pos(resolved, mt5_timeframe, 0, bars)
            if rates is None or len(rates) == 0:
                self.log_warning(f"No rates returned for {resolved} {timeframe}")
                return pd.DataFrame()
            df = pd.DataFrame(rates)
            if 'time' in df.columns:
                df['time'] = pd.to_datetime(df['time'], unit='s')
                df.set_index('time', inplace=True)
            df.columns = [col.lower() for col in df.columns]
            return df
        except Exception as exc:
            self.log_error(f"Error getting rates for {resolved} {timeframe}: {exc}")
            return pd.DataFrame()

    def get_account_info(self) -> Optional[Dict[str, Any]]:
        if not self.connected:
            return None
        try:
            info = mt5.account_info()
            if info is None:
                return None
            return {
                'login': info.login, 'balance': info.balance, 'equity': info.equity,
                'margin': info.margin, 'free_margin': info.margin_free,
                'leverage': info.leverage, 'currency': info.currency,
                'company': info.company, 'name': info.name, 'server': info.server,
                'trade_mode': info.trade_mode, 'trade_allowed': info.trade_allowed,
                'trade_expert': info.trade_expert,
            }
        except Exception as exc:
            self.log_error(f"Error getting account info: {exc}")
            return None

    def get_symbol_info(self, symbol: str) -> Optional[Dict[str, Any]]:
        if not self.connected:
            self.log_error("Not connected to MT5")
            return None
        try:
            resolved = self.resolve_symbol(symbol)
            if not resolved:
                self.log_warning(f"Symbol {symbol} not found")
                return None
            info = mt5.symbol_info(resolved)
            if info is None:
                return None
            return {
                'name': info.name,
                'bid': info.bid,
                'ask': info.ask,
                'spread': info.spread,
                'digits': info.digits,
                'point': info.point,
                'trade_contract_size': info.trade_contract_size,
                'trade_tick_size': getattr(info, 'trade_tick_size', 0.0),
                'trade_tick_value': getattr(info, 'trade_tick_value', 0.0),
                'trade_tick_value_profit': getattr(info, 'trade_tick_value_profit', 0.0),
                'trade_tick_value_loss': getattr(info, 'trade_tick_value_loss', 0.0),
                'trade_mode': info.trade_mode,
                'swap_mode': info.swap_mode,
                'margin_initial': info.margin_initial,
                'margin_maintenance': info.margin_maintenance,
                'volume_min': info.volume_min,
                'volume_max': info.volume_max,
                'volume_step': info.volume_step,
            }
        except Exception as exc:
            self.log_error(f"Error getting symbol info for {symbol}: {exc}")
            return None

    def get_full_symbol_name(self, symbol: str) -> str:
        return self.resolve_symbol(symbol) or symbol

    def get_current_price(self, symbol: str) -> Optional[Dict[str, Any]]:
        if not self.connected:
            return None
        try:
            resolved = self.resolve_symbol(symbol)
            if not resolved:
                return None
            tick = mt5.symbol_info_tick(resolved)
            if tick is None:
                return None
            return {
                'bid': tick.bid, 'ask': tick.ask, 'last': tick.last,
                'volume': tick.volume, 'time': pd.to_datetime(tick.time, unit='s'),
            }
        except Exception as exc:
            self.log_error(f"Error getting current price for {symbol}: {exc}")
            return None

    def get_multiple_symbols_data(self, symbols: List[str], timeframe: str,
                                  bars: int = 100) -> Dict[str, pd.DataFrame]:
        return {symbol: df for symbol in symbols
                if not (df := self.get_rates(symbol, timeframe, bars)).empty}

    def is_symbol_available(self, symbol: str) -> bool:
        return self.resolve_symbol(symbol) is not None if self.connected else False

    def get_server_time(self) -> Optional[datetime]:
        if not self.connected:
            return None
        try:
            resolved = self.resolve_symbol(config.SYMBOL)
            if resolved:
                tick = mt5.symbol_info_tick(resolved)
                if tick:
                    return pd.to_datetime(tick.time, unit='s').to_pydatetime()
        except Exception:
            pass
        return datetime.now()

    def place_order(self, symbol: str, order_type: int, volume: float,
                    sl: float = 0.0, tp: float = 0.0,
                    comment: str = "AI_Trader_Demo") -> Optional[int]:
        if not self.connected:
            self.log_error("Невозможно открыть ордер: нет подключения к MT5")
            return None
        if not config.DEMO_MODE:
            self.log_error("Торговля заблокирована: DEMO_MODE должен быть включен")
            return None
        try:
            resolved = self.resolve_symbol(symbol)
            if not resolved:
                self.log_error(f"Не найден символ {symbol}")
                return None
            tick = mt5.symbol_info_tick(resolved)
            if tick is None:
                return None
            price = tick.ask if order_type == mt5.ORDER_TYPE_BUY else tick.bid
            request = {
                'action': mt5.TRADE_ACTION_DEAL, 'symbol': resolved,
                'volume': volume, 'type': order_type, 'price': price,
                'sl': sl, 'tp': tp, 'deviation': 20, 'magic': 123456,
                'comment': comment, 'type_time': mt5.ORDER_TIME_GTC,
                'type_filling': mt5.ORDER_FILLING_IOC,
            }
            result = mt5.order_send(request)
            if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
                self.log_error(f"Ошибка открытия ордера {comment}: {getattr(result, 'retcode', None)} - {getattr(result, 'comment', '')}")
                return None
            self.log_info(f"Ордер успешно открыт: {result.order}, цена {price}, объем {volume}")
            return result.order
        except Exception as exc:
            self.log_error(f"Исключение при открытии ордера: {exc}")
            return None

    def __del__(self):
        try:
            self.disconnect()
        except Exception:
            pass


_mt5_connector = None


def get_mt5_connector() -> MT5Connector:
    global _mt5_connector
    if _mt5_connector is None:
        _mt5_connector = MT5Connector()
    return _mt5_connector
