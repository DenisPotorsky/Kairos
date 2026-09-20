"""Фабрика парсеров Kairos — определяет нужный парсер по содержимому файла."""

import re
from pathlib import Path

import pdfplumber
from loguru import logger

from kairos.parsers.base import BaseParser
from kairos.parsers.pdf_hall_schedule import PdfHallScheduleParser
from kairos.parsers.docx_piano_service import DocxPianoServiceParser
from kairos.parsers.docx_season import DocxSeasonParser
from kairos.parsers.excel_ugk_parser import ExcelUgkParser
from kairos.parsers.excel_choir_parser import ExcelChoirParser


_PARSER_RULES: list[tuple[list[str], str | None, type[BaseParser]]] = [
    # Консерватория (Excel)
    (["угк", "консерватория", "ugk"], ".xlsx", ExcelUgkParser),
    (["угк", "консерватория", "ugk"], ".xls", ExcelUgkParser),
    
    # Ельцин Центр: рояли (DOCX)
    (["ельцин", "роял", "piano"], ".docx", DocxPianoServiceParser),
    
    # Филармония: сезон (DOCX)
    (["сезон", "season"], ".docx", DocxSeasonParser),
    
    # Филармония: залы (PDF)
    (["зал", "hall"], ".pdf", PdfHallScheduleParser),
]

_FALLBACK_MAP: dict[str, type[BaseParser]] = {
    ".pdf": PdfHallScheduleParser,
    ".docx": DocxPianoServiceParser,
    ".xlsx": ExcelUgkParser,
    ".xls": ExcelUgkParser,
}


def _detect_choir_parser(file_path: Path) -> BaseParser | None:
    """Определяет тип графика хора по содержимому PDF."""
    try:
        with pdfplumber.open(file_path) as pdf:
            page = pdf.pages[0]
            tables = page.extract_tables()
            if not tables: return None
            
            for row in tables[0]:
                clean = [str(c).strip() if c else '' for c in row]
                if len(clean) >= 6 and 'Дата' not in clean[0] and 'СИМФОНИЧЕСКИЙ' not in clean[0]:
                    return ExcelChoirParser()
            return None
    except Exception as e:
        logger.warning(f"Не удалось определить тип хора для {file_path}: {e}")
        return None


def get_parser(file_path: Path) -> BaseParser | None:
    """Возвращает подходящий парсер для файла или None."""
    name_lower = file_path.name.lower()
    suffix = file_path.suffix.lower()

    # 1. Правила по ключевым словам
    for keywords, ext, parser_cls in _PARSER_RULES:
        if all(kw in name_lower for kw in keywords):
            if ext is None or suffix == ext:
                return parser_cls()

    # 2. Специальная логика для ph_choir (распознавание по содержимому)
    if "ph_choir" in name_lower:
        if suffix == ".xlsx" or suffix == ".xls":
            return ExcelChoirParser()
        elif suffix == ".pdf":
            choir_parser = _detect_choir_parser(file_path)
            if choir_parser:
                return choir_parser

    # 3. Fallback по расширению
    fallback_cls = _FALLBACK_MAP.get(suffix)
    if fallback_cls:
        return fallback_cls()

    return None
