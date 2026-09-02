import pandas as pd
from typing import List, Dict, Any, Optional
from utils.logger import LoggingMixin
import config


class Backtester(LoggingMixin):
    """
    Продвинутый движок бэктестинга с динамическим расчетом лота
    и проверкой ограничений брокера. (Статический SL/TP)
    """

    def __init__(self, initial_balance: float = 10000.0,
                 risk_per_trade: float = 0.01,
                 atr_sl_multiplier: float = 1.5,
                 atr_tp_multiplier: float = 3.0):
        super().__init__()
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.risk_per_trade = risk_per_trade
        self.atr_sl_multiplier = atr_sl_multiplier
        self.atr_tp_multiplier = atr_tp_multiplier
        self.trades: List[Dict[str, Any]] = []
        self.skipped_trades: List[Dict[str, Any]] = []
        self.log_info(
            f"Backtester initialized. Balance: {self.initial_balance}, "
            f"Risk per trade: {self.risk_per_trade * 100:.1f}%"
        )

    def _reset_state(self) -> None:
        """Сброс состояния для безопасного повторного использования."""
        self.balance = self.initial_balance
        self.trades = []
        self.skipped_trades = []

    def _calculate_sl_tp_atr(self, df: pd.DataFrame, entry_index: int, signal_type: str) -> tuple:
        """Рассчитывает статические SL и TP на основе ATR."""
        if 'atr_14' not in df.columns:
            self.log_error("ATR не рассчитан в DataFrame")
            return None, None

        atr_value = df.iloc[entry_index]['atr_14']
        entry_price = df.iloc[entry_index]['open']

        if pd.isna(atr_value) or pd.isna(entry_price) or atr_value <= 0:
            return None, None

        if signal_type == 'bullish':
            return (
                entry_price - (atr_value * self.atr_sl_multiplier),
                entry_price + (atr_value * self.atr_tp_multiplier)
            )
        else:
            return (
                entry_price + (atr_value * self.atr_sl_multiplier),
                entry_price - (atr_value * self.atr_tp_multiplier)
            )

    def _check_sl_tp_hit(self, df: pd.DataFrame, start_index: int,
                         sl_price: float, tp_price: float,
                         signal_type: str, max_bars: int = 100) -> Dict[str, Any]:
        """Проверяет, какой уровень (SL или TP) был достигнут первым."""
        for i in range(start_index, min(start_index + max_bars, len(df))):
            bar = df.iloc[i]
            if signal_type == 'bullish':
                if bar['low'] <= sl_price:
                    return {'result': 'loss', 'exit_price': sl_price, 'bars_held': i - start_index}
                if bar['high'] >= tp_price:
                    return {'result': 'win', 'exit_price': tp_price, 'bars_held': i - start_index}
            else:
                if bar['high'] >= sl_price:
                    return {'result': 'loss', 'exit_price': sl_price, 'bars_held': i - start_index}
                if bar['low'] <= tp_price:
                    return {'result': 'win', 'exit_price': tp_price, 'bars_held': i - start_index}

        exit_index = min(start_index + max_bars, len(df) - 1)
        return {
            'result': 'neutral',
            'exit_price': df.iloc[exit_index]['close'],
            'bars_held': exit_index - start_index,
        }

    def _get_conversion_rate(self, symbol_name: str) -> float:
        """Возвращает курс конвертации базовой валюты в RUB."""
        symbol_name = (symbol_name or '').upper()
        if symbol_name.startswith('USD'):
            return 90.0
        if symbol_name.endswith('USD'):
            rates = {'EUR': 98.0, 'GBP': 115.0, 'AUD': 60.0, 'NZD': 55.0,
                     'CHF': 100.0, 'CAD': 67.0, 'JPY': 0.60}
            return rates.get(symbol_name[:3], 90.0)
        if 'RUB' in symbol_name:
            return 1.0
        return 90.0

    def _calculate_point_value_rub(self, symbol_info: dict) -> float:
        """Рассчитывает стоимость 1 пункта в рублях для 1 лота."""
        point = symbol_info.get('point', 0.0001)
        contract_size = symbol_info.get('trade_contract_size', 100000)
        symbol_name = symbol_info.get('name', '')
        rate = self._get_conversion_rate(symbol_name)
        return point * contract_size * rate

    def _calculate_dynamic_lot(self, entry_price: float, sl_price: float,
                               symbol_info: dict) -> Optional[float]:
        """Рассчитывает динамический объем лота на основе риска."""
        volume_min = symbol_info.get('volume_min', 0.01)
        volume_max = symbol_info.get('volume_max', 100.0)
        volume_step = symbol_info.get('volume_step', 0.01)

        risk_rub = self.balance * self.risk_per_trade
        sl_distance = abs(entry_price - sl_price)

        if sl_distance == 0:
            return None

        point_value_rub = self._calculate_point_value_rub(symbol_info)
        if point_value_rub == 0:
            return None

        point = symbol_info.get('point', 0.0001)
        sl_distance_points = sl_distance / point

        lot = risk_rub / (sl_distance_points * point_value_rub)
        lot = round(lot / volume_step) * volume_step
        lot = max(volume_min, min(volume_max, lot))
        lot = round(lot, 2)

        # Проверка на минимально возможный лот
        calculated_lot_before_min = risk_rub / (sl_distance_points * point_value_rub)
        calculated_lot_before_min = round(calculated_lot_before_min / volume_step) * volume_step
        if calculated_lot_before_min < volume_min:
            return None

        return lot

    def run(self, df: pd.DataFrame, connector, signals: List[Dict[str, Any]], symbol: str = None) -> Dict[str, Any]:
        """Прогоняет сигналы с динамическим расчетом лота."""
        self._reset_state()
        test_symbol = symbol or config.SYMBOL

        if df is None or df.empty:
            self.log_error("Пустой DataFrame передан в Backtester")
            return {}

        self.log_info(f"Starting backtest with {len(signals)} signals for {test_symbol}.")

        wins = losses = neutrals = skipped = 0
        total_pnl = gross_profit = gross_loss = max_drawdown = 0.0
        peak_balance = self.initial_balance

        symbol_info = connector.get_symbol_info(test_symbol)
        if not symbol_info:
            self.log_error(f"Не удалось получить информацию о символе {test_symbol}")
            return {}

        for signal in signals:
            if not isinstance(signal, dict) or 'index' not in signal:
                continue

            entry_index = int(signal['index']) + 1
            if entry_index >= len(df):
                continue

            signal_type = signal.get('type', 'bullish')
            if signal_type not in ('bullish', 'bearish'):
                continue

            sl_price, tp_price = self._calculate_sl_tp_atr(df, entry_index, signal_type)
            if sl_price is None or tp_price is None:
                continue

            entry_price = float(df.iloc[entry_index]['open'])

            lot = self._calculate_dynamic_lot(entry_price, sl_price, symbol_info)
            if lot is None:
                skipped += 1
                self.skipped_trades.append({
                    'time': signal.get('time'),
                    'pattern': signal.get('pattern_name', 'Unknown'),
                    'type': signal_type,
                    'entry': entry_price,
                    'sl': sl_price,
                    'reason': 'lot_below_minimum'
                })
                continue

            exit_info = self._check_sl_tp_hit(df, entry_index + 1, sl_price, tp_price, signal_type)
            exit_price = float(exit_info['exit_price'])
            result = exit_info['result']

            price_diff = exit_price - entry_price if signal_type == 'bullish' else entry_price - exit_price

            point = symbol_info.get('point', 0.0001)
            contract_size = symbol_info.get('trade_contract_size', 100000)
            rate = self._get_conversion_rate(symbol_info.get('name', ''))
            pnl_rub = price_diff * contract_size * lot * rate

            spread_points = symbol_info.get('spread', 10)
            spread_cost = spread_points * point * contract_size * lot * rate
            net_pnl = pnl_rub - spread_cost

            trade_result = {
                'time': signal.get('time'),
                'pattern': signal.get('pattern_name', 'Unknown'),
                'type': signal_type,
                'entry': entry_price,
                'sl': sl_price,
                'tp': tp_price,
                'exit': exit_price,
                'lot': lot,
                'risk_rub': self.balance * self.risk_per_trade,
                'result': result,
                'pnl_rub': net_pnl,
                'bars_held': exit_info['bars_held']
            }
            self.trades.append(trade_result)

            total_pnl += net_pnl
            self.balance += net_pnl

            if net_pnl > 0:
                wins += 1
                gross_profit += net_pnl
            elif net_pnl < 0:
                losses += 1
                gross_loss += abs(net_pnl)
            else:
                neutrals += 1

            peak_balance = max(peak_balance, self.balance)
            max_drawdown = max(max_drawdown, peak_balance - self.balance)

        total_trades = wins + losses + neutrals
        win_rate = (wins / (wins + losses) * 100) if (wins + losses) > 0 else 0.0
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else float('inf')
        avg_lot = sum(t['lot'] for t in self.trades) / len(self.trades) if self.trades else 0.0

        stats = {
            'total_trades': total_trades,
            'wins': wins,
            'losses': losses,
            'neutrals': neutrals,
            'skipped_trades': skipped,
            'win_rate': f"{win_rate:.2f}%",
            'total_pnl_rub': total_pnl,
            'final_balance': self.balance,
            'avg_pnl_per_trade': total_pnl / total_trades if total_trades > 0 else 0.0,
            'gross_profit': gross_profit,
            'gross_loss': gross_loss,
            'profit_factor': f"{profit_factor:.2f}",
            'max_drawdown': max_drawdown,
            'max_drawdown_percent': f"{(max_drawdown / peak_balance * 100):.2f}%" if peak_balance else '0.00%',
            'avg_lot': avg_lot,
        }

        self.log_info(
            f"Backtest finished. W/L/N/Skipped: {wins}/{losses}/{neutrals}/{skipped}, "
            f"Win Rate: {stats['win_rate']}, PnL: {total_pnl:.2f}, "
            f"Profit Factor: {stats['profit_factor']}, Avg Lot: {avg_lot:.4f}"
        )
        return stats
