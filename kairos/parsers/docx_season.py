"""Парсер плана сезона хора из DOCX."""
import re
from datetime import datetime, timedelta
from pathlib import Path

from docx import Document

from kairos.models import Event, EventType, Priority
from kairos.parsers.base import BaseParser


class DocxSeasonParser(BaseParser):
    """Парсит план сезона из Word-документа."""

    # Регулярка для поиска дат вида "11.09" или "11 .09"
    DATE_PATTERN = re.compile(r"(\d{1,2})\s*[./]\s*(\d{1,2})")
    # Регулярка для поиска времени вида "19:00"
    TIME_PATTERN = re.compile(r"(\d{1,2}):(\d{2})")

    def parse(self, file_path: Path) -> list[Event]:
        self.validate_file(file_path, ".docx")
        events: list[Event] = []

        doc = Document(file_path)
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    new_events = self._parse_cell(cell.text, file_path.name)
                    events.extend(new_events)

        return events

    def _parse_cell(self, text: str, source: str) -> list[Event]:
        """Парсит содержимое ячейки таблицы. Одна ячейка может содержать несколько концертов."""
        if not text.strip():
            return []

        events: list[Event] = []
        # Разбиваем текст на блоки по датам
        blocks = self._split_by_dates(text)

        for block in blocks:
            event = self._parse_block(block, source)
            if event is not None:
                events.append(event)

        return events

    def _split_by_dates(self, text: str) -> list[str]:
        """Разбивает текст на блоки, каждый начинается с даты."""
        # Находим все позиции дат
        matches = list(self.DATE_PATTERN.finditer(text))
        if not matches:
            return []

        blocks: list[str] = []
        for i, match in enumerate(matches):
            start = match.start()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            blocks.append(text[start:end].strip())

        return blocks

    def _parse_block(self, block: str, source: str) -> Event | None:
        """Парсит один блок текста (один концерт)."""
        # Извлекаем дату
        date_match = self.DATE_PATTERN.search(block)
        if not date_match:
            return None

        day = int(date_match.group(1))
        month = int(date_match.group(2))

        # Определяем год: месяцы 9-12 → 2026, 1-8 → 2027
        year = 2026 if month >= 9 else 2027

        try:
            base_date = datetime(year, month, day)
        except ValueError:
            return None

        # Извлекаем время
        time_match = self.TIME_PATTERN.search(block)
        if not time_match:
            return None

        hour = int(time_match.group(1))
        minute = int(time_match.group(2))
        start = base_date.replace(hour=hour, minute=minute)
        end = start + timedelta(hours=2)  # Концерт по умолчанию 2 часа

        # Проверяем "Планируется"
        is_planned = "планируется" in block.lower()
        priority = Priority.P2 if is_planned else Priority.P0

        # Очищаем название: убираем дату, время, день недели
        title = self._clean_title(block)
        if not title:
            return None

        return Event(
            title=title,
            start=start,
            end=end,
            event_type=EventType.CONCERT,
            priority=priority,
            source_file=source,
            description="Планируется" if is_planned else "",
        )

    @staticmethod
    def _clean_title(block: str) -> str:
        """Убирает дату, время, день недели из блока, оставляя описание концерта."""
        # Убираем дату (11.09, пт,)
        cleaned = re.sub(r"\d{1,2}\s*[./]\s*\d{1,2},?\s*", "", block)
        # Убираем день недели
        cleaned = re.sub(r"(пн|вт|ср|чт|пт|сб|вск|вс),?\s*", "", cleaned, flags=re.IGNORECASE)
        # Убираем время
        cleaned = re.sub(r"\d{1,2}:\d{2},?\s*", "", cleaned)
        # Убираем "Аб." с номером
        cleaned = re.sub(r"Аб\.\s*\d*\s*", "", cleaned)
        # Чистим лишние пробелы и запятые
        cleaned = re.sub(r"[,\s]+", " ", cleaned).strip()
        return cleaned
