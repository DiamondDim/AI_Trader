"""
Generates rich chart commands for MT5 bridge.
Supports: Trendlines, Channels, Horizontal Rays (Necklines), Rectangles (Targets), and Text Labels.
"""
from pathlib import Path
from typing import Iterable, Union, List
from .models import PatternDetection, PatternPoint

# Цвета для визуализации (BGR формат MQL5)
COLORS = {
    "bullish": 0x00FF00,  # Зеленый
    "bearish": 0x0000FF,  # Красный (в MQL5 красный это 0x0000FF, но часто используют 255)
    "neutral": 0xFFFF00,  # Желтый
    "target": 0x0080FF,  # Оранжевый/Синий для целей
    "stop": 0xFF00FF,  # Пурпурный для стопов
    "neckline": 0xFFFFFF,  # Белый для важных уровней
}


def _fmt_time(t) -> str:
    """Форматирует время для MQL5 StringToTime (YYYY.MM.DD HH:MM:SS)"""
    if not t:
        return ""
    # Преобразуем datetime или строку в нужный формат
    s = str(t).replace("-", ".").replace(" ", " ")
    # Убеждаемся, что формат YYYY.MM.DD HH:MM:SS
    if len(s) < 19:
        s += " 00:00:00"
    return s[:19]


def export_mt5_commands(detections: Iterable[PatternDetection], path: Union[str, Path]) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    lines: List[str] = []

    for idx, d in enumerate(detections):
        color_base = COLORS.get(d.direction, COLORS["neutral"])
        prefix = f"{d.name}_{idx}"
        points = d.points

        # --- 1. Отрисовка основных линий паттерна ---

        # Для гармоников рисуем все плечи (X-A, A-B, B-C, C-D)
        if d.category == "harmonic":
            for i in range(len(points) - 1):
                p1, p2 = points[i], points[i + 1]
                name = f"{prefix}_Leg_{p1.name}{p2.name}"
                # Используем тонкую линию для внутренних плеч
                lines.append(
                    f"LINE|{name}|{_fmt_time(p1.time)}|{p1.price}|{_fmt_time(p2.time)}|{p2.price}|{color_base}|1|STYLE_DOT"
                )

        # Для графических паттернов (H&S, Double Top) соединяем точки контура
        elif d.category == "chart":
            for i in range(len(points) - 1):
                p1, p2 = points[i], points[i + 1]
                name = f"{prefix}_Contour_{i}"
                lines.append(
                    f"LINE|{name}|{_fmt_time(p1.time)}|{p1.price}|{_fmt_time(p2.time)}|{p2.price}|{color_base}|2|STYLE_SOLID"
                )

        # Для паттернов продолжения (Flags) рисуем канал
        elif d.category == "continuation" and len(points) >= 4:
            # Предполагаем, что точки идут: [StartHigh, StartLow, EndHigh, EndLow] или аналогично
            # Для простоты соединим 0-2 (верх) и 1-3 (низ)
            p_top_start, p_bot_start, p_top_end, p_bot_end = points[0], points[1], points[2], points[3]

            # Верхняя граница канала
            lines.append(
                f"LINE|{prefix}_Channel_Top|{_fmt_time(p_top_start.time)}|{p_top_start.price}|{_fmt_time(p_top_end.time)}|{p_top_end.price}|{color_base}|1|STYLE_DASH"
            )
            # Нижняя граница канала
            lines.append(
                f"LINE|{prefix}_Channel_Bot|{_fmt_time(p_bot_start.time)}|{p_bot_start.price}|{_fmt_time(p_bot_end.time)}|{p_bot_end.price}|{color_base}|1|STYLE_DASH"
            )

        # --- 2. Специфичная отрисовка уровней (Neckline, Targets) ---

        for lvl in d.levels:
            lvl_color = COLORS["neckline"]
            style = "STYLE_SOLID"
            is_ray = False

            if lvl.name == "neckline":
                # Neckline рисуем как луч вправо
                is_ray = True
                # Для HLINE в MQL5 нужна только цена, но мы передадим время последней точки для позиционирования текста
                last_p = points[-1]
                lines.append(
                    f"HLINE|{prefix}_Neckline|{lvl.price}|{lvl_color}|1|true|{is_ray}"
                )
            elif "target" in lvl.name.lower():
                lvl_color = COLORS["target"]
                style = "STYLE_DASHDOT"
            elif "stop" in lvl.name.lower() or "sl" in lvl.name.lower():
                lvl_color = COLORS["stop"]
                style = "STYLE_DASH"

            # Если это не Neckline (который уже обработан выше как HLINE с лучом), рисуем обычный уровень
            if lvl.name != "neckline":
                lines.append(
                    f"HLINE|{prefix}_{lvl.name}|{lvl.price}|{lvl_color}|1|false|false"
                )

            # --- 3. Текстовые метки ---
            last_p = points[-1]
            txt_name = f"{prefix}_Txt_{lvl.name}"
            # Смещаем текст немного вправо от последней точки паттерна
            lines.append(
                f"TEXT|{txt_name}|{_fmt_time(last_p.time)}|{lvl.price}|{lvl.name.upper()}|{lvl_color}|8"
            )

    target.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    return target
