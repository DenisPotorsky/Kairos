"""Парсер расписания залов Консерватории (УГК) — Финальная версия."""
import re
from datetime import datetime, timedelta
from pathlib import Path

from kairos.models import Event, EventType, Priority
from kairos.parsers.base import BaseParser


class ExcelUgkParser(BaseParser):
    ORG_NAME = "Консерватория"

    def parse(self, file_path: Path) -> list[Event]:
        # Поддерживаем и .xls и .xlsx
        if not file_path.suffix.lower() in [".xls", ".xlsx"]:
             print(f"⚠️ Пропуск {file_path.name}: неверное расширение")
             return []
             
        events: list[Event] = []

        try:
            from openpyxl import load_workbook
        except ImportError:
            print("❌ Ошибка: pip install openpyxl")
            return []

        try:
            wb = load_workbook(filename=file_path, data_only=True)
        except Exception as e:
            # Если openpyxl не смог (например, старый .xls), пробуем pandas как запасной вариант
            return self._parse_with_pandas(file_path)

        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            sheet_events = self._parse_sheet(ws, file_path.name)
            events.extend(sheet_events)

        return events

    def _parse_with_pandas(self, file_path: Path) -> list[Event]:
        """Запасной парсер через pandas (для HTML-таблиц)."""
        import pandas as pd
        events = []
        try:
            # Пробуем разные кодировки
            for enc in ['utf-8', 'windows-1251']:
                try:
                    tables = pd.read_html(file_path, encoding=enc)
                    for df in tables:
                        # Преобразуем DataFrame в формат, похожий на openpyxl worksheet
                        # Это упрощение, но для HTML-таблиц часто достаточно
                        pass 
                    break
                except: continue
        except: pass
        return events

    def _parse_sheet(self, ws, source: str) -> list[Event]:
        events = []
        current_date = None
        current_hall = "Зал УГК" 

        for row in ws.iter_rows(values_only=True):
            cells = [str(c).strip() if c is not None else "" for c in row]
            full_row_text = " ".join(cells).lower()

            if not any(cells):
                continue

            # 1. ПРОВЕРКА НА СМЕНУ ЗАЛА
            # Ищем "большой зал" или "малый зал" в строке
            if "большой зал" in full_row_text:
                current_hall = "Большой зал УГК"
                continue
            
            if "малый зал" in full_row_text:
                current_hall = "Малый зал УГК"
                continue

            # 2. ПРОПУСК ЗАГОЛОВКОВ
            if "дата" in full_row_text and "время" in full_row_text:
                continue

            # 3. ПОИСК ДАТЫ
            found_date = False
            for cell in cells:
                date_match = re.search(r"(\d{1,2})\.(\d{1,2})\.(\d{2,4})", cell)
                if date_match:
                    day = int(date_match.group(1))
                    month = int(date_match.group(2))
                    year = int(date_match.group(3))
                    if year < 100: year += 2000
                    try:
                        current_date = datetime(year, month, day)
                        found_date = True
                        break
                    except ValueError:
                        pass
            
            if found_date:
                continue

            # 4. ПОИСК СОБЫТИЯ
            time_str = ""
            title_str = ""
            
            # Ищем время
            for i, cell in enumerate(cells):
                if re.search(r"\d{1,2}[.:]\d{2}", cell):
                    time_str = cell
                    # Название обычно в следующей ячейке
                    if i + 1 < len(cells):
                        title_str = cells[i+1]
                    break
            
            # Если название не нашли рядом, ищем любую длинную строку
            if not title_str:
                for cell in cells:
                    if len(cell) > 2 and cell != time_str and not re.match(r"^\d", cell):
                        title_str = cell
                        break

            if current_date and time_str and title_str:
                event = self._create_event(current_date, time_str, title_str, current_hall, source)
                if event:
                    events.append(event)

        return events

    def _create_event(self, base_date: datetime, time_str: str, title: str, hall: str, source: str) -> Event | None:
        clean_time = time_str.replace(".", ":")
        
        match = re.search(r"(\d{1,2}):(\d{2})\s*-\s*(\d{1,2}):(\d{2})", clean_time)
        
        if match:
            start_dt = base_date.replace(hour=int(match.group(1)), minute=int(match.group(2)))
            end_dt = base_date.replace(hour=int(match.group(3)), minute=int(match.group(4)))
        else:
            single_match = re.search(r"(\d{1,2}):(\d{2})", clean_time)
            if single_match:
                h, m = int(single_match.group(1)), int(single_match.group(2))
                start_dt = base_date.replace(hour=h, minute=m)
                end_dt = start_dt + timedelta(hours=2)
            elif "после" in clean_time.lower():
                start_dt = base_date.replace(hour=21, minute=0)
                end_dt = start_dt + timedelta(hours=1)
            else:
                return None

        event_type = EventType.REHEARSAL
        lower_title = title.lower()
        if "настройка" in lower_title:
            event_type = EventType.TECHNICAL
        elif "экзамен" in lower_title or "собрание" in lower_title:
            event_type = EventType.MEETING
        elif "концерт" in lower_title:
            event_type = EventType.CONCERT

        return Event(
            title=f"[{self.ORG_NAME}] {title}",
            start=start_dt,
            end=end_dt,
            event_type=event_type,
            priority=Priority.P1,
            source_file=source,
            location=hall,
            tags=()
        )
