"""Robust MetaTrader 5 connector for market data and controlled execution."""

from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Tuple

import MetaTrader5 as mt5
import pandas as pd

import config
from utils.logger import LoggingMixin


class MT5Connector(LoggingMixin):
    """Single connection facade for all MT5 access in the project."""

    def __init__(self, login: Optional[int] = None, password: Optional[str] = None, server: Optional[str] = None):
        super().__init__()
        self.login, self.password, self.server = login, password, server
        self.connected = False
        self.timeframe_map = {'M1': mt5.TIMEFRAME_M1, 'M5': mt5.TIMEFRAME_M5, 'M15': mt5.TIMEFRAME_M15,
                              'M30': mt5.TIMEFRAME_M30, 'H1': mt5.TIMEFRAME_H1, 'H4': mt5.TIMEFRAME_H4,
                              'D1': mt5.TIMEFRAME_D1, 'W1': mt5.TIMEFRAME_W1, 'MN1': mt5.TIMEFRAME_MN1}

    @staticmethod
    def _to_moscow(value):
        if value is None:
            return value
        try:
            ts = pd.Timestamp(value)
            if ts.tzinfo is None:
                ts = ts.tz_localize('UTC')
            return ts.tz_convert('Europe/Moscow').tz_localize(None)
        except Exception:
            return value

    def _load_credentials(self, interactive: bool = True) -> Tuple[Optional[int], str, str]:
        login, password, server = config.get_mt5_credentials(interactive=interactive)
        self.login = self.login if self.login is not None else login
        self.password = self.password or password
        self.server = self.server or server
        return self.login, self.password or "", self.server or ""

    def connect(self, login: Optional[int] = None, password: Optional[str] = None,
                server: Optional[str] = None, interactive: bool = True) -> bool:
        try:
            if login is not None: self.login = login
            if password is not None: self.password = password
            if server is not None: self.server = server
            self._load_credentials(interactive=interactive)
            if self.login is None or not self.password or not self.server:
                self.log_error("MT5 credentials are not configured")
                self.connected = False
                return False
            if not mt5.initialize():
                self.log_error(f"MT5 initialization failed: {mt5.last_error()}")
                self.connected = False
                return False
            if not mt5.login(self.login, self.password, self.server, timeout=config.MT5_TIMEOUT):
                self.log_error(f"MT5 login failed: {mt5.last_error()}")
                mt5.shutdown(); self.connected = False
                return False
            self.connected = True
            self.log_info(f"Connected to MT5 (Login: {self.login}, Server: {self.server})")
            account_info = self.get_account_info()
            if account_info:
                self.log_info(f"Account balance: {account_info.get('balance', 0):.2f} {account_info.get('currency', 'USD')}")
            return True
        except Exception as exc:
            self.connected = False
            self.log_error(f"Error connecting to MT5: {exc}")
            try: mt5.shutdown()
            except Exception: pass
            return False

    def _ensure_connected(self) -> bool:
        if self.connected:
            try:
                if mt5.terminal_info() is not None:
                    return True
            except Exception:
                pass
        self.connected = False
        return self.connect(interactive=False)

    def disconnect(self) -> bool:
        try:
            mt5.shutdown()
            self.connected = False
            return True
        except Exception as exc:
            self.connected = False
            self.log_error(f"Error disconnecting from MT5: {exc}")
            return False

    def resolve_symbol(self, symbol: str) -> Optional[str]:
        if not self._ensure_connected(): return None
        try:
            direct = mt5.symbol_info(symbol)
            if direct is not None: return direct.name
            requested = (symbol or '').upper()
            for candidate in mt5.symbols_get() or []:
                if candidate.name.upper() == requested: return candidate.name
            for candidate in mt5.symbols_get() or []:
                if name_matches(requested, candidate.name.upper()): return candidate.name
        except Exception as exc:
            self.log_error(f"Error resolving symbol {symbol}: {exc}")
        return None

    def get_rates(self, symbol: str, timeframe: str, bars: int = 100) -> pd.DataFrame:
        if not self._ensure_connected():
            self.log_error("Not connected to MT5"); return pd.DataFrame()
        mt5_timeframe = self.timeframe_map.get(timeframe.upper())
        if mt5_timeframe is None:
            self.log_error(f"Unsupported timeframe: {timeframe}"); return pd.DataFrame()
        resolved = self.resolve_symbol(symbol)
        if not resolved:
            self.log_warning(f"Symbol {symbol} not found"); return pd.DataFrame()
        try:
            rates = mt5.copy_rates_from_pos(resolved, mt5_timeframe, 0, bars)
            if rates is None or len(rates) == 0:
                self.log_warning(f"No rates returned for {resolved} {timeframe}"); return pd.DataFrame()
            df = pd.DataFrame(rates)
            if 'time' in df.columns:
                df['time'] = pd.to_datetime(df['time'], unit='s', utc=True).dt.tz_convert('Europe/Moscow').dt.tz_localize(None)
                df.set_index('time', inplace=True)
            df.columns = [col.lower() for col in df.columns]
            return df
        except Exception as exc:
            self.log_error(f"Error getting rates for {resolved} {timeframe}: {exc}"); return pd.DataFrame()

    def get_account_info(self) -> Optional[Dict[str, Any]]:
        if not self._ensure_connected(): return None
        try:
            info = mt5.account_info()
            if info is None: return None
            return {'login': info.login, 'balance': info.balance, 'equity': info.equity, 'margin': info.margin,
                    'free_margin': info.margin_free, 'leverage': info.leverage, 'currency': info.currency,
                    'company': info.company, 'name': info.name, 'server': info.server, 'trade_mode': info.trade_mode,
                    'trade_allowed': info.trade_allowed, 'trade_expert': info.trade_expert}
        except Exception as exc:
            self.log_error(f"Error getting account info: {exc}"); return None

    def get_symbol_info(self, symbol: str) -> Optional[Dict[str, Any]]:
        if not self._ensure_connected(): return None
        try:
            resolved = self.resolve_symbol(symbol)
            if not resolved: return None
            info = mt5.symbol_info(resolved)
            if info is None: return None
            return {'name': info.name, 'bid': info.bid, 'ask': info.ask, 'spread': info.spread, 'digits': info.digits,
                    'point': info.point, 'trade_contract_size': info.trade_contract_size,
                    'trade_tick_size': getattr(info, 'trade_tick_size', 0.0), 'trade_tick_value': getattr(info, 'trade_tick_value', 0.0),
                    'trade_tick_value_profit': getattr(info, 'trade_tick_value_profit', 0.0),
                    'trade_tick_value_loss': getattr(info, 'trade_tick_value_loss', 0.0), 'trade_mode': info.trade_mode,
                    'swap_mode': info.swap_mode, 'margin_initial': info.margin_initial,
                    'margin_maintenance': info.margin_maintenance, 'volume_min': info.volume_min,
                    'volume_max': info.volume_max, 'volume_step': info.volume_step,
                    'filling_mode': getattr(info, 'filling_mode', 0), 'trade_stops_level': getattr(info, 'trade_stops_level', 0),
                    'trade_freeze_level': getattr(info, 'trade_freeze_level', 0)}
        except Exception as exc:
            self.log_error(f"Error getting symbol info for {symbol}: {exc}"); return None

    def get_full_symbol_name(self, symbol: str) -> str: return self.resolve_symbol(symbol) or symbol

    def get_current_price(self, symbol: str) -> Optional[Dict[str, Any]]:
        if not self._ensure_connected(): return None
        try:
            resolved = self.resolve_symbol(symbol)
            tick = mt5.symbol_info_tick(resolved) if resolved else None
            if tick is None: return None
            return {'bid': tick.bid, 'ask': tick.ask, 'last': tick.last, 'volume': tick.volume,
                    'time': self._to_moscow(pd.to_datetime(tick.time, unit='s', utc=True))}
        except Exception as exc:
            self.log_error(f"Error getting current price for {symbol}: {exc}"); return None

    def get_multiple_symbols_data(self, symbols: List[str], timeframe: str, bars: int = 100) -> Dict[str, pd.DataFrame]:
        return {symbol: df for symbol in symbols if not (df := self.get_rates(symbol, timeframe, bars)).empty}

    def is_symbol_available(self, symbol: str) -> bool:
        return self.resolve_symbol(symbol) is not None if self._ensure_connected() else False

    def get_server_time(self) -> Optional[datetime]:
        price = self.get_current_price(config.SYMBOL)
        return price['time'].to_pydatetime() if price else datetime.now(timezone.utc).astimezone().replace(tzinfo=None)

    @staticmethod
    def _select_filling_mode(symbol_info) -> int:
        mode = int(getattr(symbol_info, 'filling_mode', 0) or 0)
        if mode & getattr(mt5, 'SYMBOL_FILLING_IOC', 2): return mt5.ORDER_FILLING_IOC
        if mode & getattr(mt5, 'SYMBOL_FILLING_FOK', 1): return mt5.ORDER_FILLING_FOK
        return mt5.ORDER_FILLING_RETURN

    def place_order(self, symbol: str, order_type: int, volume: float, sl: float = 0.0, tp: float = 0.0,
                    comment: str = "AI_Trader_Demo", magic_number: int = 123456) -> Optional[int]:
        if not self._ensure_connected():
            self.log_error("Невозможно открыть ордер: нет подключения к MT5"); return None
        if not config.DEMO_MODE:
            self.log_error("Торговля заблокирована: DEMO_MODE должен быть включен"); return None
        try:
            resolved = self.resolve_symbol(symbol)
            if not resolved or volume <= 0: return None
            tick, info = mt5.symbol_info_tick(resolved), mt5.symbol_info(resolved)
            if tick is None or info is None: return None
            price = tick.ask if order_type == mt5.ORDER_TYPE_BUY else tick.bid
            request = {'action': mt5.TRADE_ACTION_DEAL, 'symbol': resolved, 'volume': float(volume), 'type': order_type,
                       'price': price, 'sl': float(sl), 'tp': float(tp), 'deviation': 20, 'magic': int(magic_number),
                       'comment': comment, 'type_time': mt5.ORDER_TIME_GTC, 'type_filling': self._select_filling_mode(info)}
            check = mt5.order_check(request)
            if check is None:
                self.log_error(f"Проверка ордера не выполнена: {mt5.last_error()}"); return None
            if getattr(check, 'retcode', 0) not in (0, getattr(mt5, 'TRADE_RETCODE_DONE', 10009)):
                self.log_error(f"Ордер отклонен проверкой: {check.retcode} - {getattr(check, 'comment', '')}"); return None
            result = mt5.order_send(request)
            if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
                self.log_error(f"Ошибка открытия ордера: {getattr(result, 'retcode', None)} - {getattr(result, 'comment', '')}"); return None
            self.log_info(f"Ордер успешно открыт: {result.order}, цена {price}, объем {volume}")
            return result.order
        except Exception as exc:
            self.log_error(f"Исключение при открытии ордера: {exc}"); return None

    def __del__(self):
        try: self.disconnect()
        except Exception: pass


def name_matches(requested: str, candidate: str) -> bool:
    if not requested or not candidate or not candidate.startswith(requested): return False
    suffix = candidate[len(requested):]
    return not suffix or all(ch.isalnum() or ch in '._-' for ch in suffix)


_mt5_connector = None


def get_mt5_connector() -> MT5Connector:
    global _mt5_connector
    if _mt5_connector is None: _mt5_connector = MT5Connector()
    return _mt5_connector
