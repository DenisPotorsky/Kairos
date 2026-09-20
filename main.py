"""Kairos — агрегатор обязательств (с поддержкой Консерватории)."""
import sys
from pathlib import Path
from loguru import logger

from kairos.parsers.factory import get_parser
from kairos.core.exporter import IcsExporter
from kairos.utils.pdf_to_excel_converter import convert_choir_pdf

# --- СТАНДАРТНЫЕ ИМЕНА ФАЙЛОВ ---
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
        print(f"  ✅ {label}: {len(events)} событий ({filename})")
        return events
    except Exception as e:
        print(f"  ❌ {label}: ошибка в '{filename}' -> {e}")
        return []

def deduplicate_events(events: list) -> list:
    seen = set()
    unique = []
    for event in events:
        key = (event.title, event.start.isoformat(), event.location or "")
        if key not in seen:
            seen.add(key)
            unique.append(event)
    removed = len(events) - len(unique)
    if removed > 0:
        print(f" 🧹 Удалено {removed} дубликатов")
    return unique

def save_ics(events: list, filename: str, cal_name: str) -> None:
    if not events:
        print("\n⚠️  Нет событий для сохранения.")
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

    # === АВТОКОНВЕРТАЦИЯ PDF ХОРА В EXCEL ===
    pdf_choir = data_dir / FILE_PH_CHOIR
    excel_choir = data_dir / FILE_PH_CHOIR_XLSX
    
    if pdf_choir.exists():
        logger.info("🔄 Обнаружен PDF графика хора. Конвертирую в Excel...")
        if convert_choir_pdf(pdf_choir, excel_choir):
            logger.info("✅ Конвертация успешна. Будет использован ph_choir.xlsx")
        else:
            logger.warning("❌ Ошибка конвертации PDF. Использую оригинальный файл.")
    elif excel_choir.exists() and not pdf_choir.exists():
        logger.info("✅ Найден готовый Excel файл графика хора (PDF не найден).")
    # ========================================

    all_events = []

    # 1. Недельные данные
    if mode in ["week", "all"]:
        print("📅 Недельный план:")
        all_events.extend(get_events(data_dir, FILE_PH_HALLS, "Залы Филармонии"))
        all_events.extend(get_events(data_dir, FILE_EC_PIANO, "Рояли ЕЦ"))
        all_events.extend(get_events(data_dir, FILE_UGK_HALLS, "Залы Консерватории"))

    # 2. Месячные/Сезонные данные
    if mode in ["season", "all"]:
        print("🗓️  Месячный план:")
        choir_file = FILE_PH_CHOIR_XLSX if excel_choir.exists() else FILE_PH_CHOIR_PDF
        all_events.extend(get_events(data_dir, choir_file, "Хор Филармонии"))
        all_events.extend(get_events(data_dir, FILE_PH_SEASON, "Сезон Филармонии"))

    output_file = f"kairos_{mode}.ics"
    save_ics(all_events, output_file, f"Kairos {mode.capitalize()}")
    # === ПОЛНАЯ ОЧИСТКА ПАПКИ DATA ПОСЛЕ СБОРКИ ===
    if all_events and Path(output_file).exists():
        logger.info("🧹 Очищаю папку data/ после успешной сборки...")
        for f in data_dir.iterdir():
            if f.is_file():
                f.unlink()
                logger.debug(f"   Удалён: {f.name}")
        logger.info("✅ Папка data/ полностью очищена")
    # ==============================================


if __name__ == "__main__":
    main()
