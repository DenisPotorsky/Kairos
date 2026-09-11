"""Абстрактный базовый класс для всех парсеров Kairos."""
from abc import ABC, abstractmethod
from pathlib import Path

from kairos.models import Event


class BaseParser(ABC):
    """
    Контракт для всех парсеров.
    Любой новый парсер обязан реализовать метод parse().
    """

    @abstractmethod
    def parse(self, file_path: Path) -> list[Event]:
        """
        Парсит файл и возвращает список событий.

        Args:
            file_path: Путь к файлу для парсинга.

        Returns:
            Список объектов Event.
        """
        ...

    def validate_file(self, file_path: Path, expected_suffix: str) -> None:
        """Проверяет существование файла и его расширение."""
        if not file_path.exists():
            raise FileNotFoundError(f"Файл не найден: {file_path}")
        if file_path.suffix.lower() != expected_suffix:
            raise ValueError(
                f"Ожидался файл {expected_suffix}, получен {file_path.suffix}"
            )
