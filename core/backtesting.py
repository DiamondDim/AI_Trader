import pandas as pd
from typing import List, Dict, Any, Optional
from utils.logger import LoggingMixin
import config


class Backtester(LoggingMixin):
    """
    Продвинутый движок бэктестинга с динамическим расчетом лота
    и проверкой ограничений брокера.
    """
    def __init__(self, initial_balance: float = 10000.0,
                 risk_per_trade: float = 0.01,  # 1% риска на сделку
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
            f"Risk per trade: {risk_per_trade*100:.1f}%"
        )

    def _calculate_sl_tp_atr(self, df: pd.DataFrame, entry_index: int, signal_type: str) -> tuple:
        """Рассчитывает SL и TP на основе ATR."""
        if 'atr_14' not in df.columns:
            self.log_error("ATR не рассчитан в DataFrame")
            return None, None

        atr_value = df.iloc[entry_index]['atr_14']
        entry_price = df.iloc[entry_index]['open']

        if signal_type == 'bullish':
            sl_price = entry_price - (atr_value * self.atr_sl_multiplier)
            tp_price = entry_price + (atr_value * self.atr_tp_multiplier)
        else:
            sl_price = entry_price + (atr_value * self.atr_sl_multiplier)
            tp_price = entry_price - (atr_value * self.atr_tp_multiplier)

        return sl_price, tp_price

    def _check_sl_tp_hit(self, df: pd.DataFrame, start_index: int,
                         sl_price: float, tp_price: float,
                         signal_type: str, max_bars: int = 50) -> Dict[str, Any]:
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
        exit_price = df.iloc[exit_index]['close']
        return {'result': 'neutral', 'exit_price': exit_price, 'bars_held': exit_index - start_index}

    def _get_conversion_rate(self, symbol_name: str) -> float:
        """Возвращает курс конвертации базовой валюты в RUB."""
        if symbol_name.startswith('USD'):
            return 90.0
        elif symbol_name.endswith('USD'):
            base_currency_rates = {
                'EUR': 98.0, 'GBP': 115.0, 'AUD': 60.0, 'NZD': 55.0,
                'CHF': 100.0, 'CAD': 67.0, 'JPY': 0.60,
            }
            base_curr = symbol_name[:3]
            return base_currency_rates.get(base_curr, 90.0)
        elif 'RUB' in symbol_name:
            return 1.0
        else:
            # Кросс-пары — используем USD как промежуточную
            return 90.0

    def _calculate_point_value_rub(self, symbol_info: dict) -> float:
        """
        Рассчитывает стоимость 1 пункта в рублях для 1 лота.
        Формула: point × contract_size × conversion_rate
        """
        point = symbol_info.get('point', 0.0001)
        contract_size = symbol_info.get('trade_contract_size', 100000)
        symbol_name = symbol_info.get('name', '')

        point_value_base = point * contract_size
        rate = self._get_conversion_rate(symbol_name)

        return point_value_base * rate

    def _calculate_dynamic_lot(self, entry_price: float, sl_price: float,
                                symbol_info: dict) -> Optional[float]:
        """
        Рассчитывает динамический объем лота на основе риска от текущего баланса.

        Формула:
            lot = (balance × risk%) / (sl_distance_points × point_value_rub)

        Returns:
            Объем лота или None, если расчет невозможен / лот меньше минимального
        """
        # Ограничения брокера
        volume_min = symbol_info.get('volume_min', 0.01)
        volume_max = symbol_info.get('volume_max', 100.0)
        volume_step = symbol_info.get('volume_step', 0.01)

        # Риск в рублях на эту сделку
        risk_rub = self.balance * self.risk_per_trade

        # Расстояние до SL в абсолютных единицах цены
        sl_distance = abs(entry_price - sl_price)
        if sl_distance == 0:
            self.log_warning("SL совпадает с ценой входа — сделка пропущена")
            return None

        # Стоимость 1 пункта в рублях для 1 лота
        point_value_rub = self._calculate_point_value_rub(symbol_info)
        if point_value_rub == 0:
            self.log_error("Не удалось рассчитать стоимость пункта")
            return None

        # Количество пунктов до SL
        point = symbol_info.get('point', 0.0001)
        sl_distance_points = sl_distance / point

        # === РАСЧЕТ ЛОТА ===
        lot = risk_rub / (sl_distance_points * point_value_rub)

        # Округление до шага объема брокера
        lot = round(lot / volume_step) * volume_step

        # Ограничение минимум/максимум
        lot = max(volume_min, min(volume_max, lot))
        lot = round(lot, 2)

        # === КРИТИЧЕСКАЯ ПРОВЕРКА ===
        # Если рассчитанный лот (до применения min) был меньше volume_min,
        # значит наш депозит слишком мал для соблюдения риск-менеджмента
        calculated_lot_before_min = risk_rub / (sl_distance_points * point_value_rub)
        calculated_lot_before_min = round(calculated_lot_before_min / volume_step) * volume_step

        if calculated_lot_before_min < volume_min:
            # Рассчитываем минимально требуемый депозит для этой сделки
            min_required_deposit = (volume_min * sl_distance_points * point_value_rub) / self.risk_per_trade
            self.log_warning(
                f"⚠️ Сделка пропущена: расчетный лот {calculated_lot_before_min:.4f} < "
                f"минимального {volume_min}. Требуемый депозит для 1% риска: "
                f"{min_required_deposit:,.0f} RUB (текущий: {self.balance:,.0f} RUB)"
            )
            return None

        return lot

    def run(self, df: pd.DataFrame, connector, signals: List[Dict[str, Any]],
            symbol: str = None) -> Dict[str, Any]:
        """Прогоняет сигналы с динамическим расчетом лота."""
        test_symbol = symbol or config.SYMBOL
        self.log_info(f"Starting backtest with {len(signals)} signals for {test_symbol}.")

        wins = 0
        losses = 0
        neutrals = 0
        skipped = 0
        total_pnl_rub = 0.0
        gross_profit = 0.0
        gross_loss = 0.0
        max_drawdown = 0.0
        peak_balance = self.initial_balance
        current_balance = self.initial_balance

        symbol_info = connector.get_symbol_info(test_symbol)
        if not symbol_info:
            self.log_error(f"Не удалось получить информацию о символе {test_symbol}")
            return {}

        self.log_info(
            f"Symbol: {symbol_info['name']}, Point: {symbol_info['point']}, "
            f"Digits: {symbol_info['digits']}, Contract Size: {symbol_info['trade_contract_size']}, "
            f"Volume Min: {symbol_info.get('volume_min')}, Volume Max: {symbol_info.get('volume_max')}, "
            f"Volume Step: {symbol_info.get('volume_step')}"
        )

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

            # === ДИНАМИЧЕСКИЙ РАСЧЕТ ЛОТА ===
            lot = self._calculate_dynamic_lot(entry_price, sl_price, symbol_info)
            if lot is None:
                skipped += 1
                self.skipped_trades.append({
                    'time': signal['time'],
                    'pattern': signal.get('pattern_name', 'Unknown'),
                    'type': signal_type,
                    'entry': entry_price,
                    'sl': sl_price,
                    'reason': 'lot_below_minimum'
                })
                continue

            exit_info = self._check_sl_tp_hit(df, entry_index + 1, sl_price, tp_price, signal_type)
            exit_price = exit_info['exit_price']
            result = exit_info['result']

            # Расчет price_diff с правильным знаком
            if signal_type == 'bullish':
                price_diff = exit_price - entry_price
            else:
                price_diff = entry_price - exit_price

            # PnL в рублях с учетом реального лота
            point = symbol_info.get('point', 0.0001)
            contract_size = symbol_info.get('trade_contract_size', 100000)
            rate = self._get_conversion_rate(symbol_info.get('name', ''))

            pnl_base = price_diff * contract_size * lot
            pnl_rub = pnl_base * rate

            # Вычитаем спред
            spread_points = symbol_info.get('spread', 10)
            spread_cost_rub = spread_points * point * contract_size * lot * rate
            net_pnl_rub = pnl_rub - spread_cost_rub

            trade_result = {
                'time': signal['time'],
                'pattern': signal.get('pattern_name', 'Unknown'),
                'type': signal_type,
                'entry': entry_price,
                'sl': sl_price,
                'tp': tp_price,
                'exit': exit_price,
                'lot': lot,
                'risk_rub': self.balance * self.risk_per_trade,
                'result': result,
                'pnl_rub': net_pnl_rub,
                'bars_held': exit_info['bars_held']
            }

            self.trades.append(trade_result)
            total_pnl_rub += net_pnl_rub
            current_balance += net_pnl_rub
            self.balance = current_balance  # Compound-эффект

            # Статистика
            if net_pnl_rub > 0:
                wins += 1
                gross_profit += net_pnl_rub
            elif net_pnl_rub < 0:
                losses += 1
                gross_loss += abs(net_pnl_rub)
            else:
                neutrals += 1

            # Максимальная просадка
            if current_balance > peak_balance:
                peak_balance = current_balance
            drawdown = peak_balance - current_balance
            if drawdown > max_drawdown:
                max_drawdown = drawdown

        total_trades = wins + losses + neutrals
        win_rate = (wins / (wins + losses) * 100) if (wins + losses) > 0 else 0
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else float('inf')
        avg_lot = sum(t['lot'] for t in self.trades) / len(self.trades) if self.trades else 0

        stats = {
            'total_trades': total_trades,
            'wins': wins,
            'losses': losses,
            'neutrals': neutrals,
            'skipped_trades': skipped,
            'win_rate': f"{win_rate:.2f}%",
            'total_pnl_rub': total_pnl_rub,
            'final_balance': self.balance,
            'avg_pnl_per_trade': total_pnl_rub / total_trades if total_trades > 0 else 0,
            'gross_profit': gross_profit,
            'gross_loss': gross_loss,
            'profit_factor': f"{profit_factor:.2f}",
            'max_drawdown': max_drawdown,
            'max_drawdown_percent': f"{(max_drawdown / peak_balance * 100):.2f}%",
            'avg_lot': avg_lot
        }

        self.log_info(
            f"Backtest finished. W/L/N/Skipped: {wins}/{losses}/{neutrals}/{skipped}, "
            f"Win Rate: {stats['win_rate']}, PnL: {total_pnl_rub:.2f} RUB, "
            f"Profit Factor: {stats['profit_factor']}, Avg Lot: {avg_lot:.4f}"
        )
        return stats
