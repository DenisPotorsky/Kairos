"""Парсер УГК с фильтром."""
import re
from datetime import datetime, timedelta
from pathlib import Path
from loguru import logger
from kairos.models import Event, EventType, Priority
from kairos.parsers.base import BaseParser

class ExcelUgkParser(BaseParser):
    ORG_NAME = "Консерватория"
    ALLOWED_KEYWORDS = ["концерт", "настройка", "экзамен", "зачет", "запись"]

    def parse(self, file_path: Path) -> list[Event]:
        if file_path.suffix.lower() not in [".xls", ".xlsx"]: return []
        try:
            from openpyxl import load_workbook
        except ImportError: return []

        events = []
        try:
            wb = load_workbook(filename=file_path, data_only=True)
            for sheet_name in wb.sheetnames:
                ws = wb[sheet_name]
                hall = "Малый зал УГК" if "малый" in sheet_name.lower() else "Большой зал УГК"
                events.extend(self._parse_sheet(ws, file_path.name, hall))
            wb.close()
            logger.info(f"✅ УГК: {len(events)} событий")
        except Exception as e:
            logger.error(f"Ошибка УГК: {e}")
        return events

    def _parse_sheet(self, ws, source: str, hall: str) -> list[Event]:
        events = []
        current_date = None
        for row in ws.iter_rows(values_only=True):
            cells = [str(c).strip() if c else "" for c in row]

            # Дата
            m = re.search(r"(\d{1,2})\.(\d{1,2})\.(\d{2,4})", cells[0])
            if m:
                try:
                    y = int(m.group(3))
                    if y < 100: y += 2000
                    current_date = datetime(y, int(m.group(2)), int(m.group(1)))
                except: pass

            if not current_date or len(cells) < 3: continue

            t_str, title = cells[1], cells[2]
            if not t_str or not title or "дата" in title.lower(): continue

            # Фильтр
            if not any(k in title.lower() for k in self.ALLOWED_KEYWORDS): continue

            # Время
            clean_t = t_str.replace(".", ":").replace(" ", "")
            m = re.search(r"(\d{1,2}):(\d{2})-(\d{1,2}):(\d{2})", clean_t)
            if m:
                s = current_date.replace(hour=int(m.group(1)), minute=int(m.group(2)))
                e = current_date.replace(hour=int(m.group(3)), minute=int(m.group(4)))
            else:
                m2 = re.search(r"(\d{1,2}):(\d{2})", clean_t)
                if not m2: continue
                s = current_date.replace(hour=int(m2.group(1)), minute=int(m2.group(2)))
                e = s + timedelta(hours=2)

            etype = EventType.REHEARSAL
            if "концерт" in title.lower(): etype = EventType.CONCERT
            elif "настройка" in title.lower(): etype = EventType.TECHNICAL
            elif "запись" in title.lower(): etype = EventType.SERVICE

            events.append(Event(
                title=f"[{self.ORG_NAME}] {title}", start=s, end=e,
                event_type=etype, priority=Priority.P1,
                source_file=source, location=hall
            ))
        return events