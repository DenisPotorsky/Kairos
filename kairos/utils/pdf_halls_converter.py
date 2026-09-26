"""Конвертер PDF плана залов Филармонии в Excel."""

import re
from pathlib import Path
import pdfplumber
from openpyxl import Workbook
from loguru import logger


def convert_halls_pdf_to_excel(pdf_path: Path, excel_path: Path) -> bool:
    """
    Извлекает текст из PDF и сохраняет в Excel.
    Структура Excel: [Дата/Контекст, Время, Описание]
    """
    try:
        wb = Workbook()
        ws = wb.active
        ws.title = "Plan"
        ws.append(["Context", "Time", "Description"])

        with pdfplumber.open(pdf_path) as pdf:
            full_text = ""
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    full_text += text + "\n"

        if not full_text:
            logger.warning("PDF пустой")
            return False

        # 1. Находим все даты в тексте (21.9, 28.09 и т.д.)
        # Это нужно, чтобы привязать события к дням
        dates = re.findall(r'\b(\d{1,2}\.\d{1,2})\b', full_text)
        # Оставляем только уникальные, сохраняя порядок (примерно)
        unique_dates = []
        for d in dates:
            if d not in unique_dates:
                # Фильтруем мусор (например, 18.30 - это время, а не дата)
                # Дата обычно имеет день <= 31
                day = int(d.split('.')[0])
                if day <= 31:
                    unique_dates.append(d)

        # 2. Разбиваем текст на блоки по датам
        # Мы будем искать позицию каждой даты в тексте и резать текст между ними
        chunks = []
        last_index = 0

        # Ищем позиции дат
        date_positions = []
        for d in unique_dates:
            # Ищем вхождение даты, которое выглядит как заголовок (не время)
            # В твоих файлах даты идут списком в начале или в сетке
            idx = full_text.find(d, last_index)
            if idx != -1:
                date_positions.append((idx, d))
                last_index = idx + len(d)

        # Если даты не нашли как блоки, просто берем весь текст как один блок (fallback)
        if not date_positions:
            chunks.append(("NO_DATE", full_text))
        else:
            for i, (start_idx, date_str) in enumerate(date_positions):
                end_idx = date_positions[i + 1][0] if i + 1 < len(date_positions) else len(full_text)
                chunk_text = full_text[start_idx:end_idx]
                chunks.append((date_str, chunk_text))

        # 3. Парсим каждый блок
        for date_str, chunk in chunks:
            lines = chunk.split('\n')
            current_time_slot = ""  # утро/день/вечер

            for line in lines:
                line = line.strip()
                if not line:
                    continue

                lower_line = line.lower()

                # Определяем слот времени
                if lower_line in ["утро", "день", "вечер"]:
                    current_time_slot = lower_line
                    continue

                # Ищем время в строке (10:00 или 10:00-14:00)
                time_match = re.search(r'(\d{1,2}:\d{2}(?:\s*-\s*\d{1,2}:\d{2})?)', line)

                if time_match:
                    time_val = time_match.group(1)
                    # Убираем время из описания
                    desc = re.sub(r'\d{1,2}:\d{2}(?:\s*-\s*\d{1,2}:\d{2})?', '', line).strip()
                    desc = re.sub(r'^\s*[-–]\s*', '', desc)  # убираем тире

                    # Сохраняем в Excel: [Дата, Время, Описание]
                    # Добавляем слот (утро/день) в описание для контекста, если нужно
                    ws.append([date_str, time_val, f"{desc} ({current_time_slot})"])
                else:
                    # Если времени нет, но строка длинная - это может быть продолжение или примечание
                    # Сохраняем без времени
                    if len(line) > 5:
                        ws.append([date_str, "", f"{line} ({current_time_slot})"])

        wb.save(excel_path)
        logger.info(f"✅ PDF конвертирован в {excel_path.name}")
        return True

    except Exception as e:
        logger.error(f"❌ Ошибка конвертации PDF залов: {e}")
        return False