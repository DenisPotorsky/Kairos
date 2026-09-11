"""Парсер графика репетиций из PDF (с поддержкой описания программы)."""
from datetime import timedelta
from pathlib import Path
import pdfplumber
from kairos.core.normalizer import parse_date, parse_time_range
from kairos.models import Event, EventType, Priority
from kairos.parsers.base import BaseParser

class PdfRehearsalParser(BaseParser):
    def parse(self, file_path: Path) -> list[Event]:
        self.validate_file(file_path, ".pdf")
        events = []
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                tables = page.extract_tables()
                for table in tables:
                    for row in table:
                        new_events = self._parse_row(row, file_path.name)
                        events.extend(new_events)
        return events

    def _parse_row(self, row: list[str | None], source: str) -> list[Event]:
        if row is None or len(row) < 4:
            return []

        date_str = (row[0] or "").strip()
        time_str = (row[2] or "").strip()
        type_str = (row[3] or "").strip()
        location = (row[4] or "").strip()
        conductor = (row[5] or "").strip()
        
        # 🆕 Берём колонку 6 (индекс 6) как описание/программу
        program_desc = (row[6] or "").strip() if len(row) > 6 else ""

        skip_keywords = ("выходной", "ип", "праздничный")
        if any(kw in date_str.lower() for kw in skip_keywords) or \
           any(kw in type_str.lower() for kw in skip_keywords):
            return []
        if not time_str or ":" not in time_str:
            return []

        base_date = parse_date(date_str)
        if not base_date: return []

        time_ranges = parse_time_range(time_str)
        if not time_ranges: return []

        types = self._split_multi_value(type_str)
        locations = self._split_multi_value(location)
        conductors = self._split_multi_value(conductor)

        while len(time_ranges) < len(types):
            time_ranges.append(time_ranges[-1])

        events = []
        for i, (start_time, end_time) in enumerate(time_ranges):
            start = base_date.replace(hour=start_time.hour, minute=start_time.minute)
            end = base_date.replace(hour=end_time.hour, minute=end_time.minute)
            if end <= start: end = start + timedelta(hours=1)

            type_idx = min(i, len(types) - 1)
            loc_idx = min(i, len(locations) - 1)
            cond_idx = min(i, len(conductors) - 1)

            event_type = self._detect_event_type(types[type_idx])
            priority = Priority.P0 if event_type == EventType.CONCERT else Priority.P1
            
            # 🆕 Если есть программа и это концерт (или просто есть описание), добавляем его
            desc = program_desc if program_desc else ""

            events.append(Event(
                title=types[type_idx],
                start=start,
                end=end,
                event_type=event_type,
                priority=priority,
                source_file=source,
                description=desc, # Сохраняем полную программу
                location=locations[loc_idx],
                tags=(conductors[cond_idx],) if conductors[cond_idx] else (),
            ))
        return events

    @staticmethod
    def _split_multi_value(value: str) -> list[str]:
        parts = value.replace("\r", "").replace("\n", "/").split("/")
        return [p.strip() for p in parts if p.strip()]

    @staticmethod
    def _detect_event_type(type_str: str) -> EventType:
        return EventType.CONCERT if "концерт" in type_str.lower() else EventType.REHEARSAL
