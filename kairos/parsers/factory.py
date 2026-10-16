"""Фабрика парсеров Kairos."""

from pathlib import Path
from loguru import logger

from kairos.parsers.base import BaseParser
from kairos.parsers.pdf_hall_schedule import PdfHallScheduleParser
from kairos.parsers.docx_piano_service import DocxPianoServiceParser
from kairos.parsers.docx_season import DocxSeasonParser
from kairos.parsers.excel_ugk_parser import ExcelUgkParser
from kairos.parsers.excel_choir_parser import ExcelChoirParser
from kairos.parsers.docx_branch_piano import DocxBranchPianoParser

def get_parser(file_path: Path) -> BaseParser | None:
    name_lower = file_path.name.lower()
    suffix = file_path.suffix.lower()

    # 1. Филиалы (branch или филиал)
    if "branch" in name_lower or "филиал" in name_lower:
        if suffix == ".docx":
            return DocxBranchPianoParser()

    # 2. Сезон / План Хора (НОВОЕ!)
    # Ловим файлы где есть "сезон" ИЛИ ("план" и "хор")
    if suffix == ".docx":
        if "сезон" in name_lower or "season" in name_lower:
            return DocxSeasonParser()
        if "план" in name_lower and "хор" in name_lower:
            return DocxSeasonParser()

    # 3. Консерватория (УГК)
    if any(k in name_lower for k in ["угк", "консерватория", "ugk"]):
        if suffix in [".xlsx", ".xls"]:
            return ExcelUgkParser()

    # 4. Ельцин Центр
    if any(k in name_lower for k in ["ельцин", "piano", "заявка"]):
        if suffix == ".docx":
            return DocxPianoServiceParser()

    # 5. Залы Филармонии (PDF)
    if any(k in name_lower for k in ["зал", "hall", "план на неделю"]):
        if suffix == ".pdf":
            return PdfHallScheduleParser()

    # 6. Хор (недельный)
    if "ph_choir" in name_lower:
        if suffix in [".xlsx", ".xls"]:
            return ExcelChoirParser()

    # Fallback (если ничего не подошло)
    if suffix == ".pdf": return PdfHallScheduleParser()
    if suffix == ".docx": return DocxPianoServiceParser()
    if suffix in [".xlsx", ".xls"]: return ExcelUgkParser()

    return None