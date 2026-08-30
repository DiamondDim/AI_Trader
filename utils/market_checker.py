"""
utils/market_checker.py
Модуль для проверки доступности рынка и торговых сессий.
Не требует внешнего API — использует данные MT5.
"""

import MetaTrader5 as mt5
from datetime import datetime, time
from typing import List, Tuple
from utils.logger import LoggingMixin

# Список основных праздников Forex (когда рынок закрыт)
# Формат: (месяц, день) — для текущего года
# Forex закрыт: 1 января, 25 декабря (Рождество)
# Примечание: даты с плавающим графиком (Пасха, День благодарения)
# нужно обновлять ежегодно или получать из внешнего источника
FOREX_HOLIDAYS_2026: List[Tuple[int, int]] = [
    (1, 1),  # Новый год
    (1, 2),  # Второй день Нового года (часто закрыт)
    (4, 3),  # Страстная пятница 2026
    (4, 6),  # Пасхальный понедельник 2026
    (5, 25),  # День поминовения (США)
    (7, 3),  # День независимости США (наблюдается)
    (7, 4),  # День независимости США
    (9, 7),  # День труда (США)
    (11, 26),  # День благодарения (США)
    (11, 27),  # Чёрная пятница (часто закрыт рано)
    (12, 25),  # Рождество
    (12, 26),  # Второй день Рождества (Boxing Day)
]


class MarketChecker(LoggingMixin):
    """Проверка доступности рынка для торговли"""

    def __init__(self):
        super().__init__()
        self._last_check_time = None
        self._last_check_result = False

    def is_weekend(self, check_time: datetime = None) -> bool:
        """
        Проверяет, является ли день выходным (суббота/воскресенье).
        Forex закрыт с 00:00 субботы до 23:59 воскресенья (МСК).
        """
        if check_time is None:
            check_time = datetime.now()

        # 5 = суббота, 6 = воскресенье
        return check_time.weekday() >= 5

    def is_forex_holiday(self, check_time: datetime = None) -> bool:
        """Проверяет, является ли день праздником Forex"""
        if check_time is None:
            check_time = datetime.now()

        return (check_time.month, check_time.day) in FOREX_HOLIDAYS_2026

    def is_market_open_for_symbol(self, symbol: str) -> bool:
        """
        Проверяет, открыт ли рынок для конкретного символа через MT5.
        Самый надёжный способ — попытаться получить актуальный тик.

        Returns:
            True — рынок открыт, можно торговать
            False — рынок закрыт или символ недоступен
        """
        try:
            # === ПРОВЕРКА 1: Получаем тик ===
            tick = mt5.symbol_info_tick(symbol)

            if tick is None:
                self.log_warning(f"Не удалось получить тик для {symbol}")
                return False

            # Если bid = 0 или ask = 0 — рынок закрыт
            if tick.bid <= 0 or tick.ask <= 0:
                self.log_info(f"Рынок для {symbol} закрыт (bid={tick.bid}, ask={tick.ask})")
                return False

            # Если spread аномально большой (> 1000% от нормального) — скорее всего, нет ликвидности
            if tick.ask > 0 and (tick.ask - tick.bid) / tick.ask > 0.1:
                self.log_warning(f"Аномально большой спред для {symbol}: {tick.ask - tick.bid}")
                return False

            # === ПРОВЕРКА 2: Режим торговли символа ===
            symbol_info = mt5.symbol_info(symbol)
            if symbol_info is None:
                self.log_warning(f"Не удалось получить информацию о символе {symbol}")
                return False

            # TRADE_MODE_FULL = 0 (полноценная торговля)
            # TRADE_MODE_CLOSEONLY = 2 (только закрытие)
            # TRADE_MODE_DISABLED = 3 (торговля запрещена)
            if symbol_info.trade_mode != 0:
                self.log_info(
                    f"Торговля по {symbol} ограничена: "
                    f"trade_mode={symbol_info.trade_mode}"
                )
                return False

            # === ПРОВЕРКА 3: Сессия торговли ===
            # Проверяем, есть ли текущее время в торговой сессии
            # (у каждого символа есть свои торговые часы)
            if not symbol_info.visible:
                self.log_info(f"Символ {symbol} не виден в Market Watch")
                return False

            return True

        except Exception as e:
            self.log_error(f"Ошибка проверки рынка для {symbol}: {e}")
            return False

    def is_trading_allowed(self, symbol: str, check_time: datetime = None) -> Tuple[bool, str]:
        """
        Комплексная проверка: можно ли торговать прямо сейчас.

        Returns:
            (разрешено: bool, причина: str)
        """
        if check_time is None:
            check_time = datetime.now()

        # === Уровень 1: День недели ===
        if self.is_weekend(check_time):
            return False, f"Выходной день ({check_time.strftime('%A')})"

        # === Уровень 2: Праздник ===
        if self.is_forex_holiday(check_time):
            return False, f"Праздник Forex ({check_time.strftime('%d.%m.%Y')})"

        # === Уровень 3: Проверка через MT5 ===
        if not self.is_market_open_for_symbol(symbol):
            return False, f"Рынок для {symbol} закрыт (проверка через MT5)"

        return True, "Рынок открыт"

    def get_next_trading_session(self, check_time: datetime = None) -> datetime:
        """
        Возвращает предполагаемое время начала следующей торговой сессии.
        Forex открывается в воскресенье в 23:00 МСК (или 22:00 зимой).
        """
        if check_time is None:
            check_time = datetime.now()

        # Если сегодня пятница после 23:00 или суббота/воскресенье
        weekday = check_time.weekday()

        if weekday == 5:  # Суббота
            # До воскресенья 23:00 МСК
            days_until_sunday = 1
        elif weekday == 6:  # Воскресенье
            days_until_sunday = 0
        elif weekday == 4 and check_time.hour >= 23:  # Пятница вечером
            days_until_sunday = 2
        else:
            # Рынок открыт, возвращаем завтра
            days_until_sunday = (6 - weekday) % 7
            if days_until_sunday == 0:
                days_until_sunday = 7

        # Следующее воскресенье 23:00 МСК
        from datetime import timedelta
        next_sunday = check_time + timedelta(days=days_until_sunday)
        next_sunday = next_sunday.replace(hour=23, minute=0, second=0, microsecond=0)

        return next_sunday


# Глобальный экземпляр
_market_checker = None


def get_market_checker() -> MarketChecker:
    """Получить или создать глобальный экземпляр MarketChecker"""
    global _market_checker
    if _market_checker is None:
        _market_checker = MarketChecker()
    return _market_checker
