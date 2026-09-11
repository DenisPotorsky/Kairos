"""Парсер расписания залов УГК (Консерватория) из Excel."""
import re
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

from kairos.models import Event, EventType, Priority
from kairos.parsers.base import BaseParser


class ExcelUgkParser(BaseParser):
    """Парсит расписание залов Konservatorii."""

    ORG_NAME = "УГК"

    def parse(self, file_path: Path) -> list[Event]:
        self.validate_file(file_path, ".xls") # Или .xlsx
        events: list[Event] = []

        # Читаем Excel. В файле УГК нет заголовков в привычном виде, 
        # структура "рваная". Используем header=None.
        try:
            df = pd.read_excel(file_path, header=None)
        except Exception as e:
            print(f"Ошибка чтения Excel: {e}")
            return events

        current_date = None
        current_hall = "Неизвестный зал"

        # Проходим по всем строкам
        for index, row in df.iterrows():
            # Очищаем ячейки от NaN и приводим к строке
            cells = [str(c).strip() if pd.notna(c) else "" for c in row]
            
            # 1. Поиск заголовка зала (Большой зал / Малый зал)
            # Обычно это первая ячейка в строке, которая содержит "зал"
            if cells[0] and "зал" in cells[0].lower():
                current_hall = cells[0]
                continue

            # 2. Поиск даты (13.09.2026 воскр.)
            # Ищем паттерн даты в первой ячейке
            date_match = re.search(r"(\d{2})\.(\d{2})\.(\d{4})", cells[0])
            if date_match:
                day = int(date_match.group(1))
                month = int(date_match.group(2))
                year = int(date_match.group(3))
                try:
                    current_date = datetime(year, month, day)
                except ValueError:
                    current_date = None
                continue

            # 3. Поиск события (Время | Название)
            # Время обычно во второй колонке (индекс 1), название в третьей (индекс 2)
            # Но иногда время может быть в первой, если дата пустая.
            # В файле УГК: Col 0 - Дата (пусто), Col 1 - Время, Col 2 - Название
            
            time_str = cells[1]
            title_str = cells[2]

            if current_date and time_str and title_str:
                event = self._parse_event(time_str, title_str, current_date, current_hall, file_path.name)
                if event:
                    events.append(event)

        return events

    def _parse_event(self, time_str: str, title: str, date: datetime, hall: str, source: str) -> Event | None:
        """Парсит время и создаёт событие."""
        
        # Парсим диапазон "12.00 - 15.00" или "07.00 - 09.00"
        # Заменяем точки на двоеточия для парсинга
        clean_time = time_str.replace(".", ":")
        
        # Паттерн для поиска времени
        match = re.search(r"(\d{1,2}):(\d{2})\s*-\s*(\d{1,2}):(\d{2})", clean_time)
        
        if match:
            start_h, start_m = int(match.group(1)), int(match.group(2))
            end_h, end_m = int(match.group(3)), int(match.group(4))
            
            start_dt = date.replace(hour=start_h, minute=start_m)
            end_dt = date.replace(hour=end_h, minute=end_m)
        else:
            # Если время одиночное "12.00" или "после"
            single_match = re.search(r"(\d{1,2}):(\d{2})", clean_time)
            if single_match:
                start_h, start_m = int(single_match.group(1)), int(single_match.group(2))
                start_dt = date.replace(hour=start_h, minute=start_m)
                end_dt = start_dt + timedelta(hours=2)
            elif "после" in time_str.lower():
                # "после" -> ставим на вечер (20:00)
                start_dt = date.replace(hour=20, minute=0)
                end_dt = start_dt + timedelta(hours=2)
            else:
                return None # Не смогли распарсить время

        # Определяем тип
        event_type = EventType.REHEARSAL
        priority = Priority.P1
        
        lower_title = title.lower()
        if "настройка" in lower_title:
            event_type = EventType.TECHNICAL
            priority = Priority.P3
        elif "концерт" in lower_title or "экзамен" in lower_title:
            event_type = EventType.CONCERT
            priority = Priority.P0
        elif "собрание" in lower_title:
            event_type = EventType.MEETING
            priority = Priority.P2

        # Формируем заголовок с префиксом организации
        full_title = f"[{self.ORG_NAME}] {title} [{hall}]"

        return Event(
            title=full_title,
            start=start_dt,
            end=end_dt,
            event_type=event_type,
            priority=priority,
            source_file=source,
            location=f"{self.ORG_NAME}, {hall}",
            description=title
        )
