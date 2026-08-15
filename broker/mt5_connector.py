"""
MetaTrader 5 connector for data retrieval and trading operations.
"""

import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Tuple
import logging

from pandas import DatetimeIndex, Series, Timestamp

import config
from utils.logger import LoggingMixin


class MT5Connector(LoggingMixin):
    """Connector for MetaTrader 5 terminal."""

    def __init__(self, login: Optional[int] = None,
                 password: Optional[str] = None,
                 server: Optional[str] = None):
        """Initialize MT5 connector.

        Args:
            login: MT5 account login
            password: MT5 account password
            server: MT5 server name
        """
        super().__init__()
        self.login = login or config.MT5_LOGIN
        self.password = password or config.MT5_PASSWORD
        self.server = server or config.MT5_SERVER
        self.connected = False

        # Timeframe mapping
        self.timeframe_map = {
            'M1': mt5.TIMEFRAME_M1,
            'M5': mt5.TIMEFRAME_M5,
            'M15': mt5.TIMEFRAME_M15,
            'M30': mt5.TIMEFRAME_M30,
            'H1': mt5.TIMEFRAME_H1,
            'H4': mt5.TIMEFRAME_H4,
            'D1': mt5.TIMEFRAME_D1,
            'W1': mt5.TIMEFRAME_W1,
            'MN1': mt5.TIMEFRAME_MN1
        }

    def connect(self, login: Optional[int] = None,
                password: Optional[str] = None,
                server: Optional[str] = None) -> bool:
        """Connect to MT5 terminal.

        Args:
            login: MT5 account login
            password: MT5 account password
            server: MT5 server name

        Returns:
            True if connection successful, False otherwise
        """
        try:
            # Update credentials if provided
            if login:
                self.login = login
            if password:
                self.password = password
            if server:
                self.server = server

            # Initialize MT5
            if not mt5.initialize():
                error = mt5.last_error()
                self.log_error(f"MT5 initialization failed: {error}")
                return False

            # Login to MT5
            if not mt5.login(self.login, self.password, self.server, timeout=config.MT5_TIMEOUT):
                error = mt5.last_error()
                self.log_error(f"MT5 login failed: {error}")
                mt5.shutdown()
                return False

            self.connected = True
            self.log_info(f"Connected to MT5 (Login: {self.login}, Server: {self.server})")

            # Print account info
            account_info = self.get_account_info()
            if account_info:
                self.log_info(f"Account balance: {account_info.get('balance', 0):.2f} "
                              f"{account_info.get('currency', 'USD')}")

            return True

        except Exception as e:
            self.log_error(f"Error connecting to MT5: {e}")
            return False

    def disconnect(self) -> bool:
        """Disconnect from MT5 terminal.

        Returns:
            True if disconnection successful, False otherwise
        """
        try:
            if self.connected:
                mt5.shutdown()
                self.connected = False
                self.log_info("Disconnected from MT5")
            return True
        except Exception as e:
            self.log_error(f"Error disconnecting from MT5: {e}")
            return False

    def get_rates(self, symbol: str, timeframe: str,
                  bars: int = 100) -> pd.DataFrame:
        """Get historical rates for a symbol.

        Args:
            symbol: Trading symbol (e.g., 'EURUSD')
            timeframe: Timeframe string (e.g., 'H1')
            bars: Number of bars to retrieve

        Returns:
            DataFrame with historical rates
        """
        if not self.connected:
            self.log_error("Not connected to MT5")
            return pd.DataFrame()

        # Map timeframe string to MT5 constant
        mt5_timeframe = self.timeframe_map.get(timeframe.upper())
        if mt5_timeframe is None:
            self.log_error(f"Unsupported timeframe: {timeframe}")
            return pd.DataFrame()

        try:
            # Get rates
            rates = mt5.copy_rates_from_pos(symbol, mt5_timeframe, 0, bars)

            if rates is None or len(rates) == 0:
                self.log_warning(f"No rates returned for {symbol} {timeframe}")
                return pd.DataFrame()

            # Convert to DataFrame
            df = pd.DataFrame(rates)

            # Convert time
            if 'time' in df.columns:
                df['time'] = pd.to_datetime(df['time'], unit='s')
                df.set_index('time', inplace=True)

            # Rename columns to lowercase
            df.columns = [col.lower() for col in df.columns]

            self.log_debug(f"Retrieved {len(df)} bars for {symbol} {timeframe}")

            return df

        except Exception as e:
            self.log_error(f"Error getting rates for {symbol} {timeframe}: {e}")
            return pd.DataFrame()

    def get_account_info(self) -> Optional[Dict[str, Any]]:
        """Get account information.

        Returns:
            Dictionary with account info, None if error
        """
        if not self.connected:
            self.log_error("Not connected to MT5")
            return None

        try:
            account_info = mt5.account_info()
            if account_info is None:
                self.log_error(f"Failed to get account info: {mt5.last_error()}")
                return None

            return {
                'login': account_info.login,
                'balance': account_info.balance,
                'equity': account_info.equity,
                'margin': account_info.margin,
                'free_margin': account_info.margin_free,
                'leverage': account_info.leverage,
                'currency': account_info.currency,
                'company': account_info.company,
                'name': account_info.name,
                'server': account_info.server,
                'trade_mode': account_info.trade_mode,
                'trade_allowed': account_info.trade_allowed,
                'trade_expert': account_info.trade_expert
            }

        except Exception as e:
            self.log_error(f"Error getting account info: {e}")
            return None

    def get_symbol_info(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get symbol information.

        Args:
            symbol: Trading symbol

        Returns:
            Dictionary with symbol info, None if error
        """
        if not self.connected:
            self.log_error("Not connected to MT5")
            return None

        try:
            symbol_info = mt5.symbol_info(symbol)
            if symbol_info is None:
                # Try to find symbol with different name
                all_symbols = mt5.symbols_get()
                for sym in all_symbols:
                    if symbol in sym.name:
                        symbol_info = sym
                        break

            if symbol_info is None:
                self.log_warning(f"Symbol {symbol} not found")
                return None

            return {
                'name': symbol_info.name,
                'bid': symbol_info.bid,
                'ask': symbol_info.ask,
                'spread': symbol_info.spread,
                'digits': symbol_info.digits,
                'point': symbol_info.point,
                'trade_contract_size': symbol_info.trade_contract_size,
                'trade_mode': symbol_info.trade_mode,
                'swap_mode': symbol_info.swap_mode,
                'margin_initial': symbol_info.margin_initial,
                'margin_maintenance': symbol_info.margin_maintenance,
                'volume_min': symbol_info.volume_min,
                'volume_max': symbol_info.volume_max,
                'volume_step': symbol_info.volume_step
            }

        except Exception as e:
            self.log_error(f"Error getting symbol info for {symbol}: {e}")
            return None

    def get_full_symbol_name(self, symbol: str) -> str:
        """Get the full symbol name as it appears in MT5.

        Args:
            symbol: Trading symbol (e.g., 'EURUSD')

        Returns:
            Full symbol name (e.g., 'EURUSD.rfd')
        """
        symbol_info = self.get_symbol_info(symbol)
        if symbol_info:
            return symbol_info['name']

        # Return original symbol if not found
        return symbol

    def get_current_price(self, symbol: str) -> dict[str, Timestamp | Series | DatetimeIndex | Any] | None:
        """Get current bid/ask price for a symbol.

        Args:
            symbol: Trading symbol

        Returns:
            Dictionary with bid and ask prices, None if error
        """
        if not self.connected:
            self.log_error("Not connected to MT5")
            return None

        try:
            symbol_info = mt5.symbol_info_tick(symbol)
            if symbol_info is None:
                self.log_error(f"Failed to get tick data for {symbol}: {mt5.last_error()}")
                return None

            return {
                'bid': symbol_info.bid,
                'ask': symbol_info.ask,
                'last': symbol_info.last,
                'volume': symbol_info.volume,
                'time': pd.to_datetime(symbol_info.time, unit='s')
            }

        except Exception as e:
            self.log_error(f"Error getting current price for {symbol}: {e}")
            return None

    def get_multiple_symbols_data(self, symbols: List[str],
                                  timeframe: str,
                                  bars: int = 100) -> Dict[str, pd.DataFrame]:
        """Get data for multiple symbols.

        Args:
            symbols: List of trading symbols
            timeframe: Timeframe string
            bars: Number of bars to retrieve

        Returns:
            Dictionary mapping symbol to DataFrame
        """
        data = {}
        for symbol in symbols:
            df = self.get_rates(symbol, timeframe, bars)
            if not df.empty:
                data[symbol] = df
            else:
                self.log_warning(f"No data for {symbol}")

        return data

    def is_symbol_available(self, symbol: str) -> bool:
        """Check if a symbol is available in MT5.

        Args:
            symbol: Trading symbol

        Returns:
            True if symbol is available, False otherwise
        """
        if not self.connected:
            return False

        try:
            symbol_info = mt5.symbol_info(symbol)
            return symbol_info is not None
        except:
            return False

    def get_server_time(self) -> Optional[datetime]:
        """Get current server time.

        Returns:
            Server datetime, None if error
        """
        if not self.connected:
            return None

        try:
            time = mt5.symbol_info_tick(config.SYMBOL).time
            return pd.to_datetime(time, unit='s')
        except:
            return datetime.now()

    def place_order(self, symbol: str, order_type: int, volume: float,
                    sl: float = 0.0, tp: float = 0.0, comment: str = "AI_Trader_Demo") -> Optional[int]:
        """
        Открывает ордер на покупку или продажу.

        Args:
            symbol: Торговый символ (например, 'EURUSDrfd')
            order_type: mt5.ORDER_TYPE_BUY или mt5.ORDER_TYPE_SELL
            volume: Объем сделки (лота)
            sl: Stop Loss (цена)
            tp: Take Profit (цена)
            comment: Комментарий к ордеру

        Returns:
            Номер тикета ордера при успехе, None при ошибке
        """
        if not self.connected:
            self.log_error("Невозможно открыть ордер: нет подключения к MT5")
            return None

        # ЖЕСТКАЯ ПРОВЕРКА ДЕМО-РЕЖИМА
        if not config.DEMO_MODE:
            self.log_error(
                "🚨 КРИТИЧЕСКАЯ ОШИБКА: Попытка торговли в РЕАЛЬНОМ режиме! Торговля заблокирована в целях безопасности.")
            return None

        try:
            # Получаем текущую цену для расчета отклонения
            tick = mt5.symbol_info_tick(symbol)
            if tick is None:
                self.log_error(f"Не удалось получить тик для {symbol}")
                return None

            # Определяем цену и тип заполнения
            if order_type == mt5.ORDER_TYPE_BUY:
                price = tick.ask
                type_filling = mt5.ORDER_FILLING_IOC
            else:
                price = tick.bid
                type_filling = mt5.ORDER_FILLING_IOC

            # Формируем запрос
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": volume,
                "type": order_type,
                "price": price,
                "sl": sl,
                "tp": tp,
                "deviation": 20,  # Максимальное отклонение цены в пунктах
                "magic": 123456,  # Уникальный номер советника
                "comment": comment,
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": type_filling,
            }

            # Отправляем запрос
            result = mt5.order_send(request)

            if result.retcode != mt5.TRADE_RETCODE_DONE:
                self.log_error(f"Ошибка открытия ордера {comment}: {result.retcode} - {result.comment}")
                return None

            self.log_info(f"✅ Ордер успешно открыт! Тикет: {result.order}, Цена: {price}, Объем: {volume}")
            return result.order

        except Exception as e:
            self.log_error(f"Исключение при открытии ордера: {e}")
            return None

    def __del__(self):
        """Destructor to ensure disconnection."""
        try:
            self.disconnect()
        except:
            pass


# Global MT5 connector instance
_mt5_connector = None


def get_mt5_connector() -> MT5Connector:
    """Get or create global MT5 connector instance.

    Returns:
        MT5Connector instance
    """
    global _mt5_connector
    if _mt5_connector is None:
        _mt5_connector = MT5Connector()
    return _mt5_connector
