"""Kairos — агрегатор обязательств."""

import sys
from pathlib import Path
from loguru import logger

from kairos.parsers.factory import get_parser
from kairos.core.exporter import IcsExporter
from kairos.utils.pdf_to_excel_converter import convert_choir_pdf
from kairos.utils.pdf_halls_converter import convert_halls_pdf_to_excel # <-- НОВЫЙ ИМПОРТ

# --- КОНСТАНТЫ ---
FILE_PH_HALLS = "ph_halls.pdf"
FILE_PH_CHOIR = "ph_choir.pdf"
FILE_PH_CHOIR_PDF = "ph_choir.pdf"
FILE_PH_CHOIR_XLSX = "ph_choir.xlsx"
FILE_PH_SEASON = "ph_season.docx"
FILE_EC_PIANO = "ec_piano.docx"
FILE_UGK_HALLS = "ugk_halls.xlsx"

def get_events(data_dir: Path, filename: str, label: str) -> list:
    file_path = data_dir / filename
    if not file_path.exists():
        return []
    parser = get_parser(file_path)
    if parser is None:
        print(f" ⚠️ {label}: нет парсера для '{filename}'")
        return []
    try:
        events = parser.parse(file_path)
        print(f" ✅ {label}: {len(events)} событий ({filename})")
        return events
    except Exception as e:
        print(f" ❌ {label}: ошибка -> {e}")
        return []

def deduplicate_events(events: list) -> list:
    seen = set()
    unique = []
    for e in events:
        key = (e.title, e.start.isoformat(), e.location or "")
        if key not in seen:
            seen.add(key)
            unique.append(e)
    removed = len(events) - len(unique)
    if removed > 0: print(f" 🧹 Удалено дубликатов: {removed}")
    return unique

def save_ics(events: list, filename: str, cal_name: str) -> None:
    if not events:
        print("\n⚠️ Нет событий для сохранения.")
        return
    events = deduplicate_events(events)
    events.sort(key=lambda e: e.start)
    exporter = IcsExporter(calendar_name=cal_name)
    exporter.add_events(events)
    exporter.save(Path(filename))
    print(f"\n💾 Сохранено в {filename}")

def main() -> None:
    data_dir = Path("data")
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"
    print(f"🚀 Kairos запущен (режим: {mode})\n")

    # === 1. КОНВЕРТАЦИЯ ХОРА ===
    pdf_choir = data_dir / FILE_PH_CHOIR_PDF
    excel_choir = data_dir / FILE_PH_CHOIR_XLSX
    if pdf_choir.exists():
        logger.info("🔄 Конвертирую хор PDF -> Excel...")
        convert_choir_pdf(pdf_choir, excel_choir)

    # === 2. КОНВЕРТАЦИЯ ЗАЛОВ ФИЛАРМОНИИ ===
    pdf_halls = data_dir / FILE_PH_HALLS
    excel_halls = data_dir / "ph_halls.xlsx"
    if pdf_halls.exists():
        logger.info("🔄 Конвертирую залы Филармонии PDF -> Excel...")
        convert_halls_pdf_to_excel(pdf_halls, excel_halls)

    all_events = []

    if mode in ["week", "all"]:
        print("📅 Недельный план:")
        # Парсим залы (теперь парсер сам найдёт .xlsx)
        all_events.extend(get_events(data_dir, FILE_PH_HALLS, "Залы Филармонии"))
        all_events.extend(get_events(data_dir, FILE_EC_PIANO, "Рояли ЕЦ"))
        all_events.extend(get_events(data_dir, FILE_UGK_HALLS, "Залы Консерватории"))

    if mode in ["season", "all"]:
        print("🗓️ Сезонный план:")
        choir_file = FILE_PH_CHOIR_XLSX if excel_choir.exists() else FILE_PH_CHOIR_PDF
        all_events.extend(get_events(data_dir, choir_file, "Хор Филармонии"))
        all_events.extend(get_events(data_dir, FILE_PH_SEASON, "Сезон Филармонии"))

    output_file = f"kairos_{mode}.ics"
    save_ics(all_events, output_file, f"Kairos {mode.capitalize()}")

    # === ОЧИСТКА DATA (ВСЕГДА) ===
    logger.info("🧹 Очищаю папку data/...")
    for f in data_dir.iterdir():
        if f.is_file() and not f.name.startswith("."):
            f.unlink()
    logger.info("✅ Папка data/ очищена")

if __name__ == "__main__":
    main()