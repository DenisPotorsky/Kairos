"""Парсер плана залов филармонии из PDF."""
import re
from datetime import datetime, timedelta
from pathlib import Path

import pdfplumber

from kairos.models import Event, EventType, Priority
from kairos.parsers.base import BaseParser


class PdfHallScheduleParser(BaseParser):
    """Парсит план залов филармонии."""

    HALL_DEFS = [
        (3, 4, "Большой зал"),
        (5, 6, "Камерный зал"),
        (7, 8, "Репетиционный зал"),
        (9, 10, "Другие залы"),
    ]

    def parse(self, file_path: Path) -> list[Event]:
        self.validate_file(file_path, ".pdf")
        all_events: list[Event] = []

        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                tables = page.extract_tables()
                for table in tables:
                    page_events = self._parse_table(table, file_path.name)
                    all_events.extend(page_events)

        return all_events

    def _parse_table(self, table: list[list[str | None]], source: str) -> list[Event]:
        """Парсит одну таблицу плана залов."""
        events: list[Event] = []

        header_row_idx = self._find_header_row(table)
        if header_row_idx is None:
            return events

        current_date: datetime | None = None

        for row in table[header_row_idx + 1:]:
            if not row or len(row) < 3:
                continue

            date_str = (row[1] or "").strip()
            time_slot = (row[2] or "").strip().lower()

            if date_str:
                parsed_date = self._parse_short_date(date_str)
                if parsed_date is not None:
                    current_date = parsed_date

            if current_date is None or time_slot not in ("утро", "день", "вечер"):
                continue

            for event_col, tech_col, hall_name in self.HALL_DEFS:
                # Событие
                if event_col < len(row):
                    cell_text = (row[event_col] or "").strip()
                    if cell_text:
                        cell_events = self._parse_cell(
                            cell_text, current_date, time_slot,
                            hall_name, source, is_tech=False
                        )
                        events.extend(cell_events)

                # Техническая запись
                if tech_col < len(row):
                    tech_text = (row[tech_col] or "").strip()
                    if tech_text:
                        tech_events = self._parse_cell(
                            tech_text, current_date, time_slot,
                            hall_name, source, is_tech=True
                        )
                        events.extend(tech_events)

            # Примечания (колонка 11)
            if len(row) > 11:
                notes = (row[11] or "").strip()
                if notes:
                    note_events = self._parse_cell(
                        notes, current_date, time_slot,
                        "Филармония", source, is_tech=False
                    )
                    events.extend(note_events)

        return events

    @staticmethod
    def _find_header_row(table: list[list[str | None]]) -> int | None:
        for idx, row in enumerate(table):
            if not row:
                continue
            for cell in row:
                if cell and "зал" in str(cell).lower():
                    return idx
        return None

    @staticmethod
    def _parse_short_date(date_str: str) -> datetime | None:
        match = re.match(r"(\d{1,2})\.(\d{1,2})", date_str.strip())
        if not match:
            return None
        day = int(match.group(1))
        month = int(match.group(2))
        try:
            return datetime(datetime.now().year, month, day)
        except ValueError:
            return None

    def _parse_cell(
        self, text: str, base_date: datetime, time_slot: str,
        hall: str, source: str, is_tech: bool
    ) -> list[Event]:
        """Парсит содержимое ячейки таблицы."""
        entries = self._split_cell_entries(text)
        events: list[Event] = []

        for entry_time, entry_desc in entries:
            start, end = self._resolve_time(entry_time, base_date, time_slot)
            event_type = self._detect_type(entry_desc, is_tech)
            priority = self._get_priority(event_type)

            events.append(Event(
                title=entry_desc.strip(),
                start=start,
                end=end,
                event_type=event_type,
                priority=priority,
                source_file=source,
                location=hall,
            ))

        return events

    @staticmethod
    def _split_cell_entries(text: str) -> list[tuple[str, str]]:
        """
        Разбивает текст ячейки на пары (время, описание).
        Строки БЕЗ времени склеиваются с предыдущей записью.
        """
        entries: list[tuple[str, str]] = []
        lines = text.replace("\r", "").split("\n")

        for line in lines:
            line = line.strip()
            if not line:
                continue

            time_match = re.match(
                r"(\d{1,2}:\d{2}(?:\s*-\s*\d{1,2}:\d{2})?)\s*(.*)", line
            )
            if time_match:
                # Новая запись с временем
                entries.append((time_match.group(1), time_match.group(2)))
            elif entries:
                # Продолжение предыдущей записи — склеиваем
                prev_time, prev_desc = entries[-1]
                entries[-1] = (prev_time, f"{prev_desc} {line}")
            # Если нет предыдущей записи и нет времени — пропускаем

        return entries

    def _resolve_time(
        self, time_str: str, base_date: datetime, time_slot: str
    ) -> tuple[datetime, datetime]:
        slot_defaults = {
            "утро": (10, 0, 2),
            "день": (14, 0, 2),
            "вечер": (18, 0, 2),
        }

        if not time_str:
            hour, minute, duration = slot_defaults.get(time_slot, (12, 0, 2))
            start = base_date.replace(hour=hour, minute=minute)
            return start, start + timedelta(hours=duration)

        time_str = re.sub(r"\s*-\s*", "-", time_str)

        if "-" in time_str:
            start_str, end_str = time_str.split("-", maxsplit=1)
            start = self._set_time(base_date, start_str)
            end = self._set_time(base_date, end_str)
        else:
            start = self._set_time(base_date, time_str)
            end = start + timedelta(hours=2)

        if end <= start:
            end = start + timedelta(hours=1)

        return start, end

    @staticmethod
    def _set_time(dt: datetime, time_str: str) -> datetime:
        parts = time_str.strip().split(":")
        return dt.replace(hour=int(parts[0]), minute=int(parts[1]))

    @staticmethod
    def _detect_type(description: str, is_tech: bool) -> EventType:
        lower = description.lower()
        if is_tech:
            return EventType.TECHNICAL
        if "концерт" in lower or "фестиваль" in lower:
            return EventType.CONCERT
        if "репетиция" in lower:
            return EventType.REHEARSAL
        if any(kw in lower for kw in (
            "уборка", "настройка", "открыть", "расстановка",
            "стульев", "плазма", "столов", "спинет", "перенести",
            "рояль", "стулья",
        )):
            return EventType.TECHNICAL
        return EventType.MEETING

    @staticmethod
    def _get_priority(event_type: EventType) -> Priority:
        match event_type:
            case EventType.CONCERT:
                return Priority.P0
            case EventType.REHEARSAL:
                return Priority.P1
            case EventType.TECHNICAL:
                return Priority.P3
            case _:
                return Priority.P2
