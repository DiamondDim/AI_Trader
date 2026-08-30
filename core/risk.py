"""Shared risk and position-sizing calculations for backtest and live execution."""

from typing import Any, Dict, Optional


class RiskCalculator:
    """Calculates position size using broker symbol metadata."""

    @staticmethod
    def point_value(symbol_info: Dict[str, Any], conversion_rate: float = 1.0) -> float:
        """Return value of one price point for one lot in account currency.

        MT5's tick_value/tick_size are preferred because they account for the
        symbol's contract specification and profit currency. The legacy
        point*contract_size fallback is kept for historical/test fixtures.
        """
        point = float(symbol_info.get("point") or 0.0)
        tick_size = float(symbol_info.get("trade_tick_size") or 0.0)
        tick_value = float(symbol_info.get("trade_tick_value") or 0.0)

        if point > 0 and tick_size > 0 and tick_value > 0:
            return (point / tick_size) * tick_value * conversion_rate

        contract_size = float(symbol_info.get("trade_contract_size") or 0.0)
        return point * contract_size * conversion_rate

    @staticmethod
    def lot_size(
        balance: float,
        risk_per_trade: float,
        entry_price: float,
        sl_price: float,
        symbol_info: Dict[str, Any],
        conversion_rate: float = 1.0,
    ) -> Optional[float]:
        """Calculate a broker-valid lot size for the requested risk."""
        point = float(symbol_info.get("point") or 0.0)
        volume_min = float(symbol_info.get("volume_min") or 0.01)
        volume_max = float(symbol_info.get("volume_max") or 100.0)
        volume_step = float(symbol_info.get("volume_step") or 0.01)

        sl_distance = abs(float(entry_price) - float(sl_price))
        if sl_distance <= 0 or point <= 0 or volume_step <= 0:
            return None

        point_value = RiskCalculator.point_value(symbol_info, conversion_rate)
        if point_value <= 0:
            return None

        risk_amount = float(balance) * float(risk_per_trade)
        raw_lot = risk_amount / ((sl_distance / point) * point_value)

        # Do not silently increase risk by forcing a too-small position to the
        # broker minimum. The caller can then record it as a skipped trade.
        if raw_lot < volume_min:
            return None

        lot = round(raw_lot / volume_step) * volume_step
        lot = min(volume_max, max(volume_min, lot))

        # Most FX brokers use 2 decimal places, while this also works for the
        # usual 0.001/0.1 steps after rounding to a conservative precision.
        precision = max(0, min(8, len(str(volume_step).rstrip("0").split(".")[-1]))) if "." in str(volume_step) else 0
        return round(lot, precision)
