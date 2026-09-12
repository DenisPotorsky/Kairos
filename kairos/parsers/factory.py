"""Фабрика парсеров Kairos — определяет нужный парсер по имени файла."""

from pathlib import Path
from kairos.parsers.base import BaseParser
from kairos.parsers.pdf_hall_schedule import PdfHallScheduleParser
from kairos.parsers.pdf_rehearsals import PdfRehearsalParser
from kairos.parsers.docx_piano_service import DocxPianoServiceParser
from kairos.parsers.docx_season import DocxSeasonParser
from kairos.parsers.excel_ugk_parser import ExcelUgkParser


# Правила: (ключевые_слова, расширение) → класс парсера
_PARSER_RULES: list[tuple[list[str], str | None, type[BaseParser]]] = [
    # Консерватория (Excel)
    (["угк", "консерватория", "ugk"], ".xlsx", ExcelUgkParser),
    (["угк", "консерватория", "ugk"], ".xls", ExcelUgkParser),
    # Филармония: залы (PDF)
    (["зал", "hall", "филармония"], ".pdf", PdfHallScheduleParser),
    # Филармония: хор (PDF)
    (["хор", "choir", "график"], ".pdf", PdfRehearsalParser),
    # Ельцин Центр: рояли (DOCX)
    (["ельцин", "роял", "piano"], ".docx", DocxPianoServiceParser),
    # Филармония: сезон (DOCX)
    (["сезон", "season"], ".docx", DocxSeasonParser),
]

# Fallback по расширению
_FALLBACK_MAP: dict[str, type[BaseParser]] = {
    ".pdf": PdfHallScheduleParser,
    ".docx": DocxPianoServiceParser,
    ".xlsx": ExcelUgkParser,
    ".xls": ExcelUgkParser,
}


def get_parser(file_path: Path) -> BaseParser | None:
    """Возвращает подходящий парсер для файла или None."""
    name_lower = file_path.name.lower()
    suffix = file_path.suffix.lower()

    # Сначала пробуем правила по ключевым словам + расширению
    for keywords, ext, parser_cls in _PARSER_RULES:
        if any(kw in name_lower for kw in keywords):
            if ext is None or suffix == ext:
                return parser_cls()

    # Fallback только по расширению
    fallback_cls = _FALLBACK_MAP.get(suffix)
    if fallback_cls:
        return fallback_cls()

    return None
