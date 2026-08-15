from datetime import datetime

def is_active_session(dt: datetime) -> bool:
    """
    Проверяет, попадает ли время в активные торговые сессии.
    Мы берем только Лондон и Нью-Йорк (с 10:00 до 23:00 по МСК).
    """
    # Считаем, что время в DataFrame уже в МСК (UTC+3)
    hour = dt.hour
    if 10 <= hour < 23:
        return True
    return False
