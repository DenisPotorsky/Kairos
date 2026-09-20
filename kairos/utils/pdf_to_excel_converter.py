"""Конвертер PDF графика СХ в Excel для надежного парсинга."""
import re
from pathlib import Path

import pdfplumber
from loguru import logger
from openpyxl import Workbook


def convert_choir_pdf(pdf_path: Path, excel_path: Path):
    """Конвертирует график СХ из PDF в Excel, разбивая сложные ячейки."""
    wb = Workbook()
    ws = wb.active
    ws.title = "График"
    
    headers = ["Дата", "ДН", "Время", "Наименование", "Место", "Хормейстер, Дирижер"]
    ws.append(headers)
    
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                tables = page.extract_tables()
                if not tables: continue
                
                for table in tables:
                    data_started = False
                    for row in table:
                        clean_row = [str(c).strip() if c else '' for c in row]
                        
                        # Ищем начало данных (пропускаем шапку)
                        if len(clean_row) >= 6 and 'Дата' in clean_row[0]:
                            data_started = True
                            continue
                        if not data_started: continue
                        
                        # Разбиваем сложные ячейки по \n или <br>
                        dates = [d.strip() for d in re.split(r'\n|<br>', clean_row[0]) if d.strip()]
                        times = [t.strip() for t in re.split(r'\n|<br>', clean_row[2]) if t.strip()]
                        names = [n.strip() for n in re.split(r'\n|<br>', clean_row[3]) if n.strip()]
                        locs = [l.strip() for l in re.split(r'\n|<br>', clean_row[4]) if l.strip()]
                        conds = [c.strip() for c in re.split(r'\n|<br>', clean_row[5]) if c.strip()]
                        
                        # Создаем отдельные строки для каждого события
                        max_items = max(len(times), len(names), 1)
                        for i in range(max_items):
                            date_val = dates[i] if i < len(dates) else (dates[0] if dates else '')
                            time_val = times[i] if i < len(times) else (times[0] if times else '')
                            name_val = names[i] if i < len(names) else (names[0] if names else '')
                            loc_val = locs[i] if i < len(locs) else (locs[0] if locs else '')
                            cond_val = conds[i] if i < len(conds) else (conds[0] if conds else '')
                            
                            ws.append([date_val, '', time_val, name_val, loc_val, cond_val])
        
        wb.save(excel_path)
        logger.info(f"PDF сконвертирован в Excel: {excel_path.name}")
        return True
    except Exception as e:
        logger.error(f"Ошибка конвертации PDF {pdf_path}: {e}")
        return False
    finally:
        wb.close()
