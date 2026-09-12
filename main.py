"""Kairos — агрегатор обязательств (с поддержкой Консерватории)."""
import sys
from pathlib import Path

from kairos.parsers.factory import get_parser # 🆕 Новый импорт
from kairos.core.exporter import IcsExporter

# --- СТАНДАРТНЫЕ ИМЕНА ФАЙЛОВ ---
FILE_PH_HALLS = "ph_halls.pdf"     # Филармония: Залы
FILE_PH_CHOIR = "ph_choir.pdf"     # Филармония: Хор
FILE_PH_SEASON = "ph_season.docx"  # Филармония: Сезон
FILE_EC_PIANO = "ec_piano.docx"    # Ельцин Центр: Рояли
FILE_UGK_HALLS = "ugk_halls.xlsx"   # 🆕 Консерватория: Залы


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
    """Удаляет дубликаты событий по title + start + location."""
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

    all_events = []

    # 1. Недельные данные
    if mode in ["week", "all"]:
        print("📅 Недельный план:")
        all_events.extend(get_events(data_dir, FILE_PH_HALLS, "Залы Филармонии"))
        all_events.extend(get_events(data_dir, FILE_EC_PIANO, "Рояли ЕЦ"))
        all_events.extend(get_events(data_dir, FILE_UGK_HALLS, "Залы Консерватории")) # 🆕

    # 2. Месячные/Сезонные данные
    if mode in ["season", "all"]:
        print("🗓️  Месячный план:")
        all_events.extend(get_events(data_dir, FILE_PH_CHOIR, "Хор Филармонии"))
        all_events.extend(get_events(data_dir, FILE_PH_SEASON, "Сезон Филармонии"))

    output_file = f"kairos_{mode}.ics"
    save_ics(all_events, output_file, f"Kairos {mode.capitalize()}")

if __name__ == "__main__":
    main()
