"""Универсальный парсер графика Симфонического хора из Excel."""
import re
from datetime import date, datetime, time, timedelta
from pathlib import Path

from loguru import logger
from openpyxl import load_workbook

from kairos.models import Event, EventType
from kairos.parsers.base import BaseParser


class ExcelChoirParser(BaseParser):
    """Парсит любой график СХ из Excel (сентябрь, октябрь и далее)."""

    def parse(self, file_path: Path) -> list[Event]:
        events = []
        try:
            wb = load_workbook(file_path, read_only=True, data_only=True)
            ws = wb.active
            
            # Находим строку заголовков
            header_row_idx = None
            for i, row in enumerate(ws.iter_rows(max_row=20)):
                cells = [str(c.value or '').strip().lower() for c in row]
                if 'дата' in cells and 'время' in cells:
                    header_row_idx = i + 1
                    break
            
            if not header_row_idx:
                logger.warning(f"Заголовки не найдены в {file_path.name}")
                return events

            # Читаем данные после заголовков
            for row in ws.iter_rows(min_row=header_row_idx + 1, values_only=True):
                clean = [str(c).strip() if c else '' for c in row]
                if len(clean) < 6: continue
                
                date_str = clean[0]
                time_cell = str(clean[2]) if clean[2] else ''
                name_cell = str(clean[3]) if clean[3] else ''
                loc_cell = str(clean[4]) if clean[4] else ''
                cond_cell = str(clean[5]) if clean[5] else ''
                
                # Фильтрация мусора
                skip_words = ['выходной', 'ип', 'вылет', 'выезд', 'рейс', 'сапсан', 'уточняется']
                if any(w in name_cell.lower() for w in skip_words): continue
                if not date_str or '?' in date_str: continue
                
                # Парсинг даты
                m = re.search(r'(\d{1,2})\s+(\w+)', date_str)
                if not m: continue
                day, month_name = int(m.group(1)), m.group(2).lower()[:3]
                months = {'сен':9,'окт':10,'ноя':11,'дек':12,'янв':1,'фев':2,
                          'мар':3,'апр':4,'май':5,'июн':6,'июл':7,'авг':8}
                month = months.get(month_name)
                if not month: continue
                
                # Защита от дублей: если это сентябрьский файл, игнорируем октябрьские даты
                current_year = getattr(self, "year", None) or datetime.now().year
                base_date = date(current_year, month, day)
                
                # Разбивка сложных ячеек по переносу строки
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
                    
                    if not n or '?' in t: continue
                    
                    # Очистка времени от приписок "(до 14:00 репзал)"
                    t_clean = re.sub(r'\(.*?\)', '', t).strip()
                    
                    tm = re.search(r'(\d{1,2}):(\d{2})', t_clean)
                    if not tm: continue
                    h, mi = int(tm.group(1)), int(tm.group(2))
                    start_dt = datetime.combine(base_date, time(h, mi))
                    
                    # Определение конца события
                    rm = re.search(r'(\d{1,2}):(\d{2})\s*-\s*(\d{1,2}):(\d{2})', t_clean)
                    if rm:
                        end_dt = datetime.combine(base_date, time(int(rm.group(3)), int(rm.group(4))))
                    else:
                        rm2 = re.search(r'(\d{1,2}):(\d{2})(\d{1,2}):(\d{2})', t_clean.replace(' ', ''))
                        if rm2 and rm2.group(1) != rm2.group(3):
                            end_dt = datetime.combine(base_date, time(int(rm2.group(3)), int(rm2.group(4))))
                        else:
                            end_dt = start_dt + timedelta(hours=1)
                    
                    is_concert = 'концерт' in n.lower()
                    event_type = EventType.CONCERT if is_concert else EventType.REHEARSAL
                    
                    events.append(Event(
                        title=f"[Филармония] {n}",
                        start=start_dt,
                        end=end_dt,
                        location=l,
                        description=f"{n}\nДирижер: {c}\nИсточник: {file_path.name}",
                        event_type=event_type,
                        priority=1,
                        source_file=file_path.name
                    ))
            
            wb.close()
            logger.info(f"ExcelChoirParser: {len(events)} событий из {file_path.name}")
        except Exception as e:
            logger.error(f"Ошибка парсинга Excel {file_path}: {e}")
        return events
