"""Shared market calendar helpers."""

from datetime import datetime, time
from typing import Optional

TRADING_START_MSK = time(7, 0)
TRADING_END_MSK = time(22, 0)


def is_weekday(dt: datetime) -> bool:
    return dt.weekday() < 5


def is_active_session(dt: datetime) -> bool:
    """Broker trading window: Monday-Friday, 07:00-22:00 Moscow time."""
    if not is_weekday(dt):
        return False
    return TRADING_START_MSK <= dt.time() < TRADING_END_MSK


def is_market_analysis_time(dt: datetime) -> bool:
    """Historical/analysis data is not restricted by the broker trading window."""
    return is_weekday(dt)


def next_trading_session_start(dt: datetime) -> Optional[datetime]:
    """Return the next broker trading-session start in the same naive timezone."""
    from datetime import timedelta
    candidate = dt.replace(hour=7, minute=0, second=0, microsecond=0)
    if is_weekday(dt) and dt.time() < TRADING_START_MSK:
        return candidate
    days = 1
    while (dt + timedelta(days=days)).weekday() >= 5:
        days += 1
    return (dt + timedelta(days=days)).replace(hour=7, minute=0, second=0, microsecond=0)
