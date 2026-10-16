"""Парсер плана роялей в филиалах Филармонии."""

import re
from datetime import datetime, timedelta
from pathlib import Path
from loguru import logger
from docx import Document
from kairos.models import Event, EventType, Priority
from kairos.parsers.base import BaseParser

class DocxBranchPianoParser(BaseParser):
    ORG_NAME = "Филиалы"
    ALLOWED_PHRASE = "настройка рояля"

    def parse(self, file_path: Path) -> list[Event]:
        self.validate_file(file_path, ".docx")
        events = []
        try:
            doc = Document(file_path)
            for table in doc.tables:
                for row in table.rows:
                    cells = [cell.text.strip() for cell in row.cells]
                    if len(cells) < 4 or "Дата" in cells[0]: continue
                    
                    full_row_text = " ".join(cells).lower()
                    if self.ALLOWED_PHRASE not in full_row_text: continue

                    event = self._parse_row(cells, file_path.name)
                    if event: events.append(event)
        except Exception as e:
            logger.error(f"Ошибка парсинга филиалов: {e}")
        
        logger.info(f"✅ Филиалы: {len(events)} событий")
        return events

    def _parse_row(self, cells, source):
        date_str, location, participants, instrument = cells[0], cells[1], cells[2], cells[3]
        m = re.search(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", date_str)
        if not m: return None
        
        try:
            base_date = datetime(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        except: return None

        # Возвращаем рабочее время 14:00 - 16:00
        start_dt = base_date.replace(hour=14, minute=0)
        end_dt = start_dt + timedelta(hours=2)

        return Event(
            title=f"[{self.ORG_NAME}] Настройка рояля ({location})",
            start=start_dt, 
            end=end_dt,
            event_type=EventType.SERVICE, 
            priority=Priority.P2,
            source_file=source, 
            location=location,
            description=f"{participants}\n{instrument}", 
            tags=(participants,)
        )
