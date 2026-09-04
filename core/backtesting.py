import pandas as pd
from typing import List, Dict, Any, Optional
from utils.logger import LoggingMixin
from core.risk import RiskCalculator
import config


class Backtester(LoggingMixin):
    """Backtesting engine with shared position sizing and broker constraints."""

    def __init__(self, initial_balance: float = 10000.0, risk_per_trade: float = 0.01,
                 atr_sl_multiplier: float = 1.5, atr_tp_multiplier: float = 3.0):
        super().__init__()
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.risk_per_trade = risk_per_trade
        self.atr_sl_multiplier = atr_sl_multiplier
        self.atr_tp_multiplier = atr_tp_multiplier
        self.trades: List[Dict[str, Any]] = []
        self.skipped_trades: List[Dict[str, Any]] = []
        self.log_info(f"Backtester initialized. Balance: {self.initial_balance}, Risk per trade: {self.risk_per_trade * 100:.1f}%")

    def _reset_state(self) -> None:
        self.balance = self.initial_balance
        self.trades = []
        self.skipped_trades = []

    def _calculate_sl_tp_atr(self, df: pd.DataFrame, entry_index: int, signal_type: str) -> tuple:
        if 'atr_14' not in df.columns:
            self.log_error("ATR не рассчитан в DataFrame")
            return None, None
        atr_value = df.iloc[entry_index]['atr_14']
        entry_price = df.iloc[entry_index]['open']
        if pd.isna(atr_value) or pd.isna(entry_price) or atr_value <= 0:
            return None, None
        if signal_type == 'bullish':
            return entry_price - atr_value * self.atr_sl_multiplier, entry_price + atr_value * self.atr_tp_multiplier
        return entry_price + atr_value * self.atr_sl_multiplier, entry_price - atr_value * self.atr_tp_multiplier

    def _check_sl_tp_hit(self, df: pd.DataFrame, start_index: int, sl_price: float,
                         tp_price: float, signal_type: str, max_bars: int = 100) -> Dict[str, Any]:
        """Check first SL/TP hit; if both occur in one bar, SL wins."""
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
        return {'result': 'neutral', 'exit_price': df.iloc[exit_index]['close'], 'bars_held': exit_index - start_index}

    def _get_conversion_rate(self, symbol_name: str) -> float:
        symbol_name = (symbol_name or '').upper()
        if symbol_name.startswith('USD'):
            return 90.0
        if symbol_name.endswith('USD'):
            return {'EUR': 98.0, 'GBP': 115.0, 'AUD': 60.0, 'NZD': 55.0,
                    'CHF': 100.0, 'CAD': 67.0, 'JPY': 0.60}.get(symbol_name[:3], 90.0)
        if 'RUB' in symbol_name:
            return 1.0
        return 90.0

    def _calculate_point_value_rub(self, symbol_info: dict) -> float:
        tick_value = float(symbol_info.get('trade_tick_value') or 0.0)
        tick_size = float(symbol_info.get('trade_tick_size') or 0.0)
        point = float(symbol_info.get('point') or 0.0)
        if tick_value > 0 and tick_size > 0 and point > 0:
            return (point / tick_size) * tick_value
        return RiskCalculator.point_value(symbol_info, self._get_conversion_rate(symbol_info.get('name', '')))

    def _calculate_dynamic_lot(self, entry_price: float, sl_price: float, symbol_info: dict) -> Optional[float]:
        has_tick_value = bool(symbol_info.get('trade_tick_value')) and bool(symbol_info.get('trade_tick_size'))
        conversion_rate = 1.0 if has_tick_value else self._get_conversion_rate(symbol_info.get('name', ''))
        lot = RiskCalculator.lot_size(self.balance, self.risk_per_trade, entry_price, sl_price, symbol_info, conversion_rate)
        if lot is None:
            self.log_warning("Сделка пропущена: невозможно соблюсти риск с учетом ограничений объема")
        return lot

    def run(self, df: pd.DataFrame, connector, signals: List[Dict[str, Any]], symbol: str = None) -> Dict[str, Any]:
        self._reset_state()
        test_symbol = symbol or config.SYMBOL
        if df is None or df.empty:
            self.log_error("Пустой DataFrame передан в Backtester")
            return {}
        self.log_info(f"Starting backtest with {len(signals)} signals for {test_symbol}.")
        wins = losses = neutrals = skipped = 0
        total_pnl = gross_profit = gross_loss = max_drawdown = max_drawdown_percent = 0.0
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
                self.skipped_trades.append({'time': signal.get('time'), 'pattern': signal.get('pattern_name', 'Unknown'),
                    'type': signal_type, 'entry': entry_price, 'sl': sl_price, 'reason': 'lot_below_minimum'})
                continue

            exit_info = self._check_sl_tp_hit(df, entry_index + 1, sl_price, tp_price, signal_type)
            exit_price = float(exit_info['exit_price'])
            result = exit_info['result']
            price_diff = exit_price - entry_price if signal_type == 'bullish' else entry_price - exit_price
            tick_value = float(symbol_info.get('trade_tick_value') or 0.0)
            tick_size = float(symbol_info.get('trade_tick_size') or 0.0)
            if tick_value > 0 and tick_size > 0:
                pnl_rub = (price_diff / tick_size) * tick_value * lot
                spread_cost = float(symbol_info.get('spread') or 0.0) * float(symbol_info.get('point') or 0.0) / tick_size * tick_value * lot
            else:
                rate = self._get_conversion_rate(symbol_info.get('name', ''))
                contract_size = float(symbol_info.get('trade_contract_size') or 100000)
                point = float(symbol_info.get('point') or 0.0001)
                pnl_rub = price_diff * contract_size * lot * rate
                spread_cost = float(symbol_info.get('spread') or 0.0) * point * contract_size * lot * rate
            net_pnl = pnl_rub - spread_cost
            trade_result = {'time': signal.get('time'), 'pattern': signal.get('pattern_name', 'Unknown'), 'type': signal_type,
                'entry': entry_price, 'sl': sl_price, 'tp': tp_price, 'exit': exit_price, 'lot': lot,
                'risk_rub': self.balance * self.risk_per_trade, 'result': result, 'pnl_rub': net_pnl,
                'bars_held': exit_info['bars_held']}
            self.trades.append(trade_result)
            total_pnl += net_pnl
            self.balance += net_pnl

            # Classification follows the actual exit event. Timeout/neutral
            # remains neutral regardless of whether its PnL is positive/negative.
            if result == 'win':
                wins += 1
                if net_pnl >= 0:
                    gross_profit += net_pnl
                else:
                    gross_loss += abs(net_pnl)
            elif result == 'loss':
                losses += 1
                if net_pnl >= 0:
                    gross_profit += net_pnl
                else:
                    gross_loss += abs(net_pnl)
            else:
                neutrals += 1

            peak_balance = max(peak_balance, self.balance)
            current_drawdown = max(0.0, peak_balance - self.balance)
            current_dd_percent = (current_drawdown / peak_balance * 100) if peak_balance else 0.0
            if current_drawdown > max_drawdown:
                max_drawdown = current_drawdown
                max_drawdown_percent = current_dd_percent

        total_trades = wins + losses + neutrals
        win_rate = wins / (wins + losses) * 100 if wins + losses else 0.0
        profit_factor = gross_profit / gross_loss if gross_loss else float('inf')
        avg_lot = sum(t['lot'] for t in self.trades) / len(self.trades) if self.trades else 0.0
        stats = {'total_trades': total_trades, 'wins': wins, 'losses': losses, 'neutrals': neutrals, 'skipped_trades': skipped,
            'win_rate': f"{win_rate:.2f}%", 'total_pnl_rub': total_pnl, 'final_balance': self.balance,
            'avg_pnl_per_trade': total_pnl / total_trades if total_trades else 0.0, 'gross_profit': gross_profit,
            'gross_loss': gross_loss, 'profit_factor': f"{profit_factor:.2f}", 'max_drawdown': max_drawdown,
            'max_drawdown_percent': f"{max_drawdown_percent:.2f}%", 'avg_lot': avg_lot}
        self.log_info(f"Backtest finished. W/L/N/Skipped: {wins}/{losses}/{neutrals}/{skipped}, Win Rate: {stats['win_rate']}, "
                      f"PnL: {total_pnl:.2f}, Profit Factor: {stats['profit_factor']}, Avg Lot: {avg_lot:.4f}")
        return stats
