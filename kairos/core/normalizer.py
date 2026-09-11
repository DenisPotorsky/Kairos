"""Нормализация дат и времён из сырых строк PDF."""
import re
from datetime import datetime, time


MONTH_MAP = {
    "янв": 1, "фев": 2, "мар": 3, "апр": 4,
    "май": 5, "июн": 6, "июл": 7, "авг": 8,
    "сен": 9, "окт": 10, "ноя": 11, "дек": 12,
}


def parse_date(date_str: str, year: int = 2026) -> datetime | None:
    """Парсит дату вида '26 фев', '1 сен' в datetime."""
    parts = date_str.strip().split()
    if len(parts) < 2:
        return None

    try:
        day = int(parts[0])
    except ValueError:
        return None

    month_key = parts[1].lower().rstrip(".")
    month = MONTH_MAP.get(month_key)
    if month is None:
        return None

    try:
        return datetime(year, month, day)
    except ValueError:
        return None


def parse_time_range(time_str: str) -> list[tuple[time, time]]:
    """
    Парсит диапазон(ы) времени.
    Умеет очищать мусор в скобках: '10:00-15:00(до 14:00)' -> 10:00-15:00
    """
    results: list[tuple[time, time]] = []
    
    # Убираем всё, что в скобках (например "(до 14:00 репзал)")
    clean_text = re.sub(r"\(.*?\)", "", time_str)
    # Убираем переносы строк
    lines = clean_text.replace("\r", "").split("\n")

    for line in lines:
        line = line.strip()
        if not line:
            continue

        if "-" in line:
            start_str, end_str = line.split("-", maxsplit=1)
            # Дополнительная очистка концов строк от мусора
            start_str = re.split(r"[^\d:]", start_str)[0]
            end_str = re.split(r"[^\d:]", end_str)[0]
            
            try:
                results.append((_parse_time(start_str), _parse_time(end_str)))
            except (ValueError, IndexError):
                continue
        else:
            # Одиночное время
            clean_line = re.split(r"[^\d:]", line)[0]
            try:
                t = _parse_time(clean_line)
                if t is not None:
                    results.append((t, t))
            except (ValueError, IndexError):
                continue

    return results


def _parse_time(time_str: str) -> time:
    """Парсит время вида '11:00'."""
    time_str = time_str.strip()
    if ":" not in time_str:
        raise ValueError(f"No colon in time: {time_str}")
    parts = time_str.split(":")
    return time(int(parts[0]), int(parts[1]))
