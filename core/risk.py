"""Shared risk and position-sizing calculations for backtest and live execution."""

import math
from typing import Any, Dict, Optional


class RiskCalculator:
    """Calculates position size using broker symbol metadata."""

    @staticmethod
    def point_value(symbol_info: Dict[str, Any], conversion_rate: float = 1.0) -> float:
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
        """Calculate a broker-valid lot size without rounding risk upward."""
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
        if raw_lot < volume_min:
            return None

        # Always round down to the broker's volume step so the requested risk
        # is never increased solely by position-size quantization.
        lot = math.floor((raw_lot + volume_step * 1e-9) / volume_step) * volume_step
        if lot < volume_min:
            return None
        lot = min(volume_max, lot)
        step_text = f"{volume_step:.8f}".rstrip("0")
        precision = len(step_text.split(".")[1]) if "." in step_text else 0
        return round(lot, min(8, precision))
