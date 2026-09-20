"""Парсер графика репетиций Симфонического хора за октябрь."""
import re
from datetime import date, datetime, time, timedelta
from pathlib import Path

import pdfplumber
from loguru import logger

from kairos.models import Event, EventType
from kairos.parsers.base import BaseParser


class PdfChoirOctoberParser(BaseParser):
    """Парсит октябрьский график хора (6 колонок, сложное время, рейсы)."""

    def parse(self, file_path: Path) -> list[Event]:
        events = []
        try:
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    tables = page.extract_tables()
                    if not tables: continue
                    
                    for table in tables:
                        data_started = False
                        for row in table:
                            clean = [str(c).strip() if c else '' for c in row]
                            if len(clean) >= 6 and 'Дата' in clean[0] and 'Время' in clean[2]:
                                data_started = True
                                continue
                            if not data_started: continue
                            
                            events.extend(self._parse_row(clean, file_path.name))
            logger.info(f"Октябрь: {len(events)} событий из {file_path.name}")
        except Exception as e:
            logger.error(f"Ошибка парсинга октября {file_path}: {e}")
        return events

    def _parse_row(self, row: list, source: str) -> list[Event]:
        events = []
        if len(row) < 6: return events
        
        date_str = row[0]
        time_cell = row[2]
        name_cell = row[3]
        loc_cell = row[4]
        cond_cell = row[5]
        
        # Пропускаем выходные, ИП, рейсы, выезды
        skip = ['выходной', 'ип', 'вылет', 'выезд', 'рейс']
        if any(w in name_cell.lower() for w in skip): return events
        
        # Дата
        m = re.search(r'(\d{1,2})\s+(\w+)', date_str)
        if not m: return events
        day, month_name = int(m.group(1)), m.group(2).lower()[:3]
        months = {'сен': 9, 'окт': 10, 'ноя': 11, 'дек': 12, 'янв': 1, 'фев': 2, 
                  'мар': 3, 'апр': 4, 'май': 5, 'июн': 6, 'июл': 7, 'авг': 8}
        month = months.get(month_name)
        if not month: return events
        base_date = date(getattr(self, "year", None) or datetime.now().year, month, day)
        
        # Разбивка по \n
        times = [t.strip() for t in re.split(r'\n', time_cell) if t.strip()]
        names = [n.strip() for n in re.split(r'\n', name_cell) if n.strip()]
        locs = [l.strip() for l in re.split(r'\n', loc_cell) if l.strip()]
        conds = [c.strip() for c in re.split(r'\n', cond_cell) if c.strip()]
        
        max_items = max(len(times), len(names), 1)
        for i in range(max_items):
            t = times[i] if i < len(times) else (times[0] if times else '')
            n = names[i] if i < len(names) else (names[0] if names else '')
            l = locs[i] if i < len(locs) else (locs[0] if locs else '')
            c = conds[i] if i < len(conds) else (conds[0] if conds else '')
            
            if not n or '?' in t or 'уточняется' in t.lower(): continue
            
            # Парсинг времени
            tm = re.search(r'(\d{1,2}):(\d{2})', t)
            if not tm: continue
            h, mi = int(tm.group(1)), int(tm.group(2))
            start_dt = datetime.combine(base_date, time(h, mi))
            
            # Поиск конца времени
            rm = re.search(r'(\d{1,2}):(\d{2})\s*-\s*(\d{1,2}):(\d{2})', t)
            if rm:
                end_dt = datetime.combine(base_date, time(int(rm.group(3)), int(rm.group(4))))
            else:
                rm2 = re.search(r'(\d{1,2}):(\d{2})(\d{1,2}):(\d{2})', t.replace(' ', '').replace('-', ''))
                if rm2 and rm2.group(1) != rm2.group(3):
                    end_dt = datetime.combine(base_date, time(int(rm2.group(3)), int(rm2.group(4))))
                else:
                    end_dt = start_dt + timedelta(hours=1)
            
            # Определение типа события
            is_concert = 'концерт' in n.lower()
            event_type = EventType.CONCERT if is_concert else EventType.REHEARSAL
            
            events.append(Event(
                title=f"[Филармония] {n}",
                start=start_dt,
                end=end_dt,
                location=l,
                description=f"{n}\nДирижер: {c}\nИсточник: {source}",
                event_type=event_type,
                priority=1,
                source_file=source
            ))
        return events
