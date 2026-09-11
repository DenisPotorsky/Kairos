"""Парсер плана обслуживания роялей (Ельцин Центр) из DOCX."""
import re
from datetime import datetime, timedelta
from pathlib import Path

from docx import Document

from kairos.models import Event, EventType, Priority
from kairos.parsers.base import BaseParser


class DocxPianoServiceParser(BaseParser):
    """Парсит план настройки роялей для Ельцин Центра."""

    # Название организации для отображения в календаре
    ORG_NAME = "Ельцин Центр"

    def parse(self, file_path: Path) -> list[Event]:
        self.validate_file(file_path, ".docx")
        events: list[Event] = []

        doc = Document(file_path)
        
        for table in doc.tables:
            for row in table.rows:
                cells = [cell.text.strip() for cell in row.cells]
                
                # Пропускаем заголовки и пустые/короткие строки
                if len(cells) < 4 or "Дата" in cells[0] or not cells[0]:
                    continue
                
                event = self._parse_row(cells, file_path.name)
                if event:
                    events.append(event)

        return events

    def _parse_row(self, cells: list[str], source: str) -> Event | None:
        """Парсит строку: Дата | Время | Инструмент | Работы."""
        date_str_raw = cells[0]
        time_str_raw = cells[1]
        instrument = cells[2]
        work_desc = cells[3]

        # 1. Парсим дату (очищаем от пробелов: "0 4 . 0 9" -> "04.09")
        clean_date = re.sub(r"\s+", "", date_str_raw)
        date_match = re.search(r"(\d{2})\.(\d{2})", clean_date)
        
        if not date_match:
            return None

        day = int(date_match.group(1))
        month = int(date_match.group(2))
        
        try:
            base_date = datetime(2026, month, day)
        except ValueError:
            return None

        # 2. Парсим время ("До 10:00" -> 09:00-10:00)
        time_match = re.search(r"(\d{1,2}):(\d{2})", time_str_raw)
        
        if time_match:
            hour = int(time_match.group(1))
            minute = int(time_match.group(2))
            end_time = base_date.replace(hour=hour, minute=minute)
            start_time = end_time - timedelta(hours=1)
        else:
            start_time = base_date.replace(hour=9, minute=0)
            end_time = base_date.replace(hour=11, minute=0)

        # 3. Формируем событие с пометкой организации
        # Заголовок: [Ельцин Центр] 🎹 Steinway, Pearl River
        title = f"[{self.ORG_NAME}] 🎹 {instrument}"
        
        # Описание: Полный текст работ + Источник
        full_description = f"{work_desc}\n\nИсточник: {source}"

        return Event(
            title=title,
            start=start_time,
            end=end_time,
            event_type=EventType.SERVICE,
            priority=Priority.P1, 
            source_file=source,
            description=full_description,
            location=self.ORG_NAME, # В поле локации тоже пишем Ельцин Центр
            tags=(instrument,)
        )
