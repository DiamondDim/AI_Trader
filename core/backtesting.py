import pandas as pd
from typing import List, Dict, Any
from utils.logger import LoggingMixin
import config


class Backtester(LoggingMixin):
    """
    Продвинутый движок бэктестинга с ATR-based SL/TP.
    """

    def __init__(self, initial_balance: float = 10000.0,
                 risk_per_trade: float = 0.01,
                 lot_size: float = 0.01,
                 risk_reward_ratio: float = 2.0,
                 atr_sl_multiplier: float = 1.5,  # SL = 1.5 * ATR
                 atr_tp_multiplier: float = 3.0):  # TP = 3.0 * ATR (R:R 1:2)
        super().__init__()
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.risk_per_trade = risk_per_trade
        self.lot_size = lot_size
        self.risk_reward_ratio = risk_reward_ratio
        self.atr_sl_multiplier = atr_sl_multiplier
        self.atr_tp_multiplier = atr_tp_multiplier
        self.trades: List[Dict[str, Any]] = []
        self.log_info(
            f"Backtester initialized. Balance: {self.initial_balance}, ATR SL: {atr_sl_multiplier}x, TP: {atr_tp_multiplier}x")

    def _calculate_sl_tp_atr(self, df: pd.DataFrame, entry_index: int, signal_type: str) -> tuple:
        """
        Рассчитывает SL и TP на основе ATR (волатильности).
        """
        if 'atr_14' not in df.columns:
            self.log_error("ATR не рассчитан в DataFrame")
            return None, None

        atr_value = df.iloc[entry_index]['atr_14']
        entry_price = df.iloc[entry_index]['open']

        if signal_type == 'bullish':
            sl_price = entry_price - (atr_value * self.atr_sl_multiplier)
            tp_price = entry_price + (atr_value * self.atr_tp_multiplier)
        else:  # bearish
            sl_price = entry_price + (atr_value * self.atr_sl_multiplier)
            tp_price = entry_price - (atr_value * self.atr_tp_multiplier)

        return sl_price, tp_price

    def _check_sl_tp_hit(self, df: pd.DataFrame, start_index: int,
                         sl_price: float, tp_price: float,
                         signal_type: str, max_bars: int = 50) -> Dict[str, Any]:
        """
        Проверяет, какой уровень (SL или TP) был достигнут первым.
        """
        for i in range(start_index, min(start_index + max_bars, len(df))):
            bar = df.iloc[i]

            if signal_type == 'bullish':
                if bar['low'] <= sl_price:
                    return {'result': 'loss', 'exit_price': sl_price, 'bars_held': i - start_index}
                if bar['high'] >= tp_price:
                    return {'result': 'win', 'exit_price': tp_price, 'bars_held': i - start_index}
            else:  # bearish
                if bar['high'] >= sl_price:
                    return {'result': 'loss', 'exit_price': sl_price, 'bars_held': i - start_index}
                if bar['low'] <= tp_price:
                    return {'result': 'win', 'exit_price': tp_price, 'bars_held': i - start_index}

        exit_index = min(start_index + max_bars, len(df) - 1)
        exit_price = df.iloc[exit_index]['close']
        return {'result': 'neutral', 'exit_price': exit_price, 'bars_held': exit_index - start_index}

    def run(self, df: pd.DataFrame, connector, signals: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Прогоняет сигналы с ATR-based SL/TP.
        """
        self.log_info(
            f"Starting backtest with {len(signals)} signals. ATR SL: {self.atr_sl_multiplier}x, TP: {self.atr_tp_multiplier}x")

        wins = 0
        losses = 0
        neutrals = 0
        total_pnl_rub = 0.0

        symbol_info = connector.get_symbol_info(config.SYMBOL)
        if not symbol_info:
            self.log_error("Не удалось получить информацию о символе")
            return {}

        contract_size = symbol_info.get('trade_contract_size', 100000)
        eurrub_rate = 90.0

        for signal in signals:
            entry_index = signal['index'] + 1
            if entry_index >= len(df):
                continue

            signal_type = signal.get('type', 'bullish')

            if signal_type not in ['bullish', 'bearish']:
                continue

            sl_price, tp_price = self._calculate_sl_tp_atr(df, entry_index, signal_type)
            if sl_price is None or tp_price is None:
                continue

            entry_price = df.iloc[entry_index]['open']

            exit_info = self._check_sl_tp_hit(df, entry_index + 1, sl_price, tp_price, signal_type)
            exit_price = exit_info['exit_price']
            result = exit_info['result']

            if signal_type == 'bullish':
                price_diff = exit_price - entry_price
            else:
                price_diff = entry_price - exit_price

            pnl_usd = price_diff * contract_size * self.lot_size
            pnl_rub = pnl_usd * eurrub_rate

            spread_cost_rub = 0.0002 * contract_size * self.lot_size * eurrub_rate
            net_pnl_rub = pnl_rub - spread_cost_rub

            trade_result = {
                'time': signal['time'],
                'pattern': signal.get('pattern_name', 'Unknown'),
                'type': signal_type,
                'entry': entry_price,
                'sl': sl_price,
                'tp': tp_price,
                'exit': exit_price,
                'result': result,
                'pnl_rub': net_pnl_rub,
                'bars_held': exit_info['bars_held']
            }

            self.trades.append(trade_result)
            total_pnl_rub += net_pnl_rub

            if result == 'win':
                wins += 1
            elif result == 'loss':
                losses += 1
            else:
                neutrals += 1

        total_trades = wins + losses + neutrals
        win_rate = (wins / (wins + losses) * 100) if (wins + losses) > 0 else 0
        self.balance += total_pnl_rub

        stats = {
            'total_trades': total_trades,
            'wins': wins,
            'losses': losses,
            'neutrals': neutrals,
            'win_rate': f"{win_rate:.2f}%",
            'total_pnl_rub': total_pnl_rub,
            'final_balance': self.balance,
            'avg_pnl_per_trade': total_pnl_rub / total_trades if total_trades > 0 else 0
        }

        self.log_info(
            f"Backtest finished. W/L/N: {wins}/{losses}/{neutrals}, Win Rate: {stats['win_rate']}, PnL: {total_pnl_rub:.2f} RUB")
        return stats
