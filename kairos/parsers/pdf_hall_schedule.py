"""Парсер плана залов филармонии — версия для недельных планов (PDF)."""

import re
from datetime import datetime, timedelta
from pathlib import Path
from loguru import logger
import pdfplumber

from kairos.models import Event, EventType, Priority
from kairos.parsers.base import BaseParser


class PdfHallScheduleParser(BaseParser):
    ORG_NAME = "Филармония"
    ALLOWED_KEYWORDS = ["петренко", "рояль", "спинет"]

    def parse(self, file_path: Path) -> list[Event]:
        self.validate_file(file_path, ".pdf")
        events = []

        try:
            with pdfplumber.open(file_path) as pdf:
                full_text = ""
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        full_text += text + "\n"

            if not full_text:
                return []

            # 1. Ищем диапазон дат в заголовке: 2026-43(19.10-25.10)
            # Или просто 19.10-25.10
            date_range_match = re.search(r'(\d{1,2})\.(\d{1,2})\s*-\s*(\d{1,2})\.(\d{1,2})', full_text)

            week_dates = {} # {'пн': datetime, 'вт': datetime, ...}

            if date_range_match:
                d1 = int(date_range_match.group(1))
                m1 = int(date_range_match.group(2))
                d2 = int(date_range_match.group(3))
                m2 = int(date_range_match.group(4))

                year = datetime.now().year
                start_date = datetime(year, m1, d1)

                # Заполняем словарь дней недели
                days_map = ['пн', 'вт', 'ср', 'чт', 'пт', 'сб', 'вс']
                for i, day_name in enumerate(days_map):
                    current_date = start_date + timedelta(days=i)
                    # Проверка на переход через месяц (упрощенная)
                    if i > 0 and current_date.day == d2 and current_date.month != m1:
                         # Если перешли на следующий месяц, дата уже правильная из timedelta
                         pass
                    week_dates[day_name] = current_date

            # Если не нашли диапазон, пробуем найти отдельные даты (старая логика)
            if not week_dates:
                raw_dates = re.findall(r'\b(\d{1,2})\.(\d{1,2})\b', full_text)
                unique_dates = sorted(list(set([(int(d), int(m)) for d, m in raw_dates if 1<=int(d)<=31])))
                # Пытаемся сопоставить с днями недели по порядку
                days_map = ['пн', 'вт', 'ср', 'чт', 'пт', 'сб', 'вс']
                for i, (d, m) in enumerate(unique_dates[:7]):
                    if i < len(days_map):
                        week_dates[days_map[i]] = datetime(datetime.now().year, m, d)

            if not week_dates:
                logger.warning("Не удалось определить даты недели")
                return []

            # 2. Парсим текст по блокам дней недели
            # Ищем блоки, начинающиеся с пн, вт, ср...
            # В твоем PDF текст идет потоком, но дни недели встречаются как маркеры

            lines = full_text.split('\n')
            current_day = None

            for line in lines:
                lower_line = line.lower().strip()

                # Проверяем, не началась ли новая секция дня
                # В файле дни недели могут быть в начале строки или отдельно
                for day_key in week_dates.keys():
                    if day_key in lower_line and len(lower_line) < 10: # Короткая строка с днем недели
                        current_day = day_key
                        break

                # Если день определен, ищем события
                if current_day:
                    base_date = week_dates[current_day]

                    # Фильтр по ключевым словам
                    if not any(kw in lower_line for kw in self.ALLOWED_KEYWORDS):
                        continue

                    # Ищем время
                    time_match = re.search(r'(\d{1,2}):(\d{2})(?:\s*-\s*(\d{1,2}):(\d{2}))?', line)

                    if time_match:
                        h1, m1 = int(time_match.group(1)), int(time_match.group(2))
                        start_dt = base_date.replace(hour=h1, minute=m1)

                        if time_match.group(3) and time_match.group(4):
                            h2, m2 = int(time_match.group(3)), int(time_match.group(4))
                            end_dt = base_date.replace(hour=h2, minute=m2)
                        else:
                            end_dt = start_dt + timedelta(hours=2)

                        title = re.sub(r'\d{1,2}:\d{2}(?:\s*-\s*\d{1,2}:\d{2})?', '', line).strip()
                        title = re.sub(r'^\s*[-–]\s*', '', title)

                        etype = EventType.REHEARSAL
                        if 'концерт' in lower_line: etype = EventType.CONCERT
                        elif any(k in lower_line for k in ['настройка', 'спинет', 'рояль']): etype = EventType.TECHNICAL

                        events.append(Event(
                            title=f"[{self.ORG_NAME}] {title}",
                            start=start_dt,
                            end=end_dt,
                            event_type=etype,
                            priority=Priority.P1,
                            source_file=file_path.name,
                            location="Филармония"
                        ))

        except Exception as e:
            logger.error(f"Ошибка парсинга {file_path.name}: {e}")

        logger.info(f"✅ Залы Филармонии: {len(events)} событий")
        return events