"""Базовые модели данных Kairos."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class EventType(Enum):
    CONCERT = "concert"
    REHEARSAL = "rehearsal"
    SERVICE = "service"
    MEETING = "meeting"
    TECHNICAL = "technical"   # уборка, настройка органа, открытие входа
    BUFFER = "buffer"


class Priority(Enum):
    P0 = 0
    P1 = 1
    P2 = 2
    P3 = 3


@dataclass(frozen=True)
class Event:
    title: str
    start: datetime
    end: datetime
    event_type: EventType
    priority: Priority
    source_file: str
    description: str = ""
    location: str = ""
    tags: tuple[str, ...] = field(default_factory=tuple)
