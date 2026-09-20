"""Экспорт событий в формат iCalendar (.ics)."""
from datetime import timedelta
from pathlib import Path

from icalendar import Alarm, Calendar, Event as IcsEvent

from kairos.models import Event


TYPE_EMOJI = {
    "concert": "🎤",
    "rehearsal": "🎵",
    "service": "🔧",
    "meeting": "💼",
    "technical": "⚙️",
    "buffer": "🚗",
}

# Напоминания по приоритетам (timedelta)
PRIORITY_ALARMS = {
    0: [timedelta(hours=-24), timedelta(hours=-1)],   # P0: за 24ч и за 1ч
    1: [timedelta(hours=-2)],                          # P1: за 2ч
    2: [timedelta(hours=-1)],                          # P2: за 1ч
    3: [timedelta(minutes=-30)],                       # P3: за 30мин
}


class IcsExporter:
    """Экспортирует список событий Kairos в .ics файл."""

    def __init__(self, calendar_name: str = "Kairos Schedule"):
        self._cal = Calendar()
        self._cal.add("prodid", "-//Kairos//RU")
        self._cal.add("version", "2.0")
        self._cal.add("calscale", "GREGORIAN")
        self._cal.add("x-wr-calname", calendar_name)

    def add_events(self, events: list[Event]) -> None:
        """Добавляет события в календарь."""
        for event in events:
            ics_event = self._to_ics(event)
            self._cal.add_component(ics_event)

    def save(self, output_path: Path) -> None:
        """Сохраняет .ics файл на диск."""
        with open(output_path, "wb") as f:
            f.write(self._cal.to_ical())
        print(f"✅ Файл сохранён: {output_path}")
        print(f"   Размер: {output_path.stat().st_size} байт")

    @staticmethod
    def _to_ics(event: Event) -> IcsEvent:
        """Конвертирует событие Kairos в iCalendar Event."""
        emoji = TYPE_EMOJI.get(event.event_type.value, "📌")
        title = f"{emoji} {event.title}"

        if event.location:
            title = f"{title} [{event.location}]"

        ics = IcsEvent()
        ics.add("summary", title)
        ics.add("dtstart", event.start)
        ics.add("dtend", event.end)
        ics.add("uid", f"{event.source_file}_{event.start.isoformat()}_{hash(event.title)}@kairos")

        # Описание
        desc_parts = []
        if event.description:
            desc_parts.append(event.description)
        if event.tags:
            desc_parts.append(f"Дирижёр/Ответственный: {', '.join(event.tags)}")
        desc_parts.append(f"Источник: {event.source_file}")
        desc_parts.append(f"Приоритет: {event.priority}")
        ics.add("description", "\n".join(desc_parts))

        if event.location:
            ics.add("location", event.location)

        # Напоминания через timedelta
        alarms = PRIORITY_ALARMS.get(event.priority, [timedelta(hours=-1)])
        for trigger in alarms:
            alarm = Alarm()
            alarm.add("action", "DISPLAY")
            alarm.add("description", f"Напоминание: {event.title}")
            alarm.add("trigger", trigger)
            ics.add_component(alarm)

        return ics
