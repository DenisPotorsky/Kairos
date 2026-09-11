"""
Kairos Telegram Bot v3.3 — с поддержкой Консерватории (УГК).
"""
import asyncio
import logging
import sys
import os
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import FSInputFile
from aiogram.utils.keyboard import ReplyKeyboardBuilder

# Импортируем константы из main.py
from main import (
    FILE_PH_HALLS, FILE_PH_CHOIR, FILE_EC_PIANO, FILE_PH_SEASON,
    FILE_UGK_HALLS # 🆕 Новый импорт
)

# --- НАСТРОЙКИ ---
API_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
DATA_DIR = Path("data")
BATCH_DELAY = 7

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

if not API_TOKEN:
    logger.critical("❌ ОШИБКА: Токен не найден! Проверьте файл .env")
    sys.exit(1)

bot = Bot(token=API_TOKEN)
dp = Dispatcher()
batch_task = None

# --- КЛАВИАТУРА ---
def get_main_keyboard():
    builder = ReplyKeyboardBuilder()
    builder.button(text="📅 Сегодня")
    builder.button(text="🔄 Обновить")
    builder.button(text="🏠 Главная")
    builder.adjust(2, 1) 
    return builder.as_markup(resize_keyboard=True, input_field_placeholder="Меню Kairos...")

WELCOME_TEXT = (
    "👋 **Привет! Я бот Kairos.**\n\n"
    "📥 **Как пользоваться:**\n"
    "Просто пришлите файлы (можно сразу несколько). "
    f"Я подожду {BATCH_DELAY} сек после последнего файла и обновлю календарь.\n\n"
    "📂 **Имена файлов:**\n"
    "• Залы Филармонии → `ph_halls.pdf`\n"
    "• Хор → `ph_choir.pdf`\n"
    "• Рояли ЕЦ → `ec_piano.docx`\n"
    "• Залы Консерватории → `ugk_halls.xls` 🆕\n\n"
    "👇 Используйте кнопки ниже:"
)

# --- ЛОГИКА СБОРКИ ---

def get_today_events_text():
    """Собирает события на сегодня из всех файлов."""
    # Здесь мы просто вызываем main.py через subprocess в run_batch_update,
    # но для /today нам нужно быстро прочитать файлы.
    # Чтобы не дублировать код парсеров здесь, импортируем их напрямую.
    
    from kairos.parsers.pdf_hall_schedule import PdfHallScheduleParser
    from kairos.parsers.pdf_rehearsals import PdfRehearsalParser
    from kairos.parsers.docx_piano_service import DocxPianoServiceParser
    from kairos.parsers.docx_season import DocxSeasonParser
    from kairos.parsers.excel_ugk_parser import ExcelUgkParser # 🆕 Импорт парсера

    all_events = []
    parsers_map = {
        FILE_PH_HALLS: PdfHallScheduleParser,
        FILE_PH_CHOIR: PdfRehearsalParser,
        FILE_EC_PIANO: DocxPianoServiceParser,
        FILE_PH_SEASON: DocxSeasonParser,
        FILE_UGK_HALLS: ExcelUgkParser, # 🆕 Добавляем в карту парсеров
    }

    for filename, parser_cls in parsers_map.items():
        file_path = DATA_DIR / filename
        if file_path.exists():
            try:
                events = parser_cls().parse(file_path)
                all_events.extend(events)
            except Exception as e:
                logger.error(f"Ошибка парсинга {filename}: {e}")

    today = datetime.now().date()
    # today = datetime(2026, 9, 14).date() # Для теста (понедельник)
    
    today_events = [e for e in all_events if e.start.date() == today]
    today_events.sort(key=lambda x: x.start)

    if not today_events:
        return f"🗓 **{today.strftime('%d.%m.%Y')}**\n\nСегодня событий нет. Отдыхайте! ☕️"

    lines = [f"🗓 **План на {today.strftime('%d.%m')}**\n"]
    type_emoji = {"concert": "🎤", "rehearsal": "🎵", "service": "🎹", "technical": "⚙️", "meeting": "💼"}

    for e in today_events:
        emoji = type_emoji.get(e.event_type.value, "📌")
        time_str = e.start.strftime("%H:%M")
        loc = f"[{e.location}]" if e.location else ""
        lines.append(f"{emoji} **{time_str}** {e.title} {loc}")

    return "\n".join(lines)

async def run_batch_update(message: types.Message):
    global batch_task
    batch_task = None 
    
    logger.info("⏳ Таймер истёк. Запуск пересборки...")
    await message.answer("🔄 Файлы загружены. Пересобираю календарь...")
    
    try:
        import subprocess
        result = subprocess.run([sys.executable, "main.py", "all"], capture_output=True, text=True)
        
        if result.returncode == 0:
            ics_file = Path("kairos_all.ics")
            if ics_file.exists():
                await message.answer_document(
                    FSInputFile(ics_file),
                    caption="✅ Календарь обновлён! Импортируйте этот файл."
                )
            else:
                await message.answer("❌ Файл .ics не найден.")
        else:
            await message.answer(f"❌ Ошибка сборки:\n{result.stderr[:200]}")
            
    except Exception as e:
        logger.exception("Ошибка при обновлении")
        await message.answer(f"❌ Критическая ошибка: {e}")

def schedule_batch_update(message: types.Message):
    global batch_task
    if batch_task and not batch_task.done():
        batch_task.cancel()
        logger.info("🔄 Таймер сброшен (новый файл).")
    
    loop = asyncio.get_event_loop()
    batch_task = loop.create_task(delayed_update(message))

async def delayed_update(message: types.Message):
    try:
        await asyncio.sleep(BATCH_DELAY)
        await run_batch_update(message)
    except asyncio.CancelledError:
        pass

# --- ОБРАБОТЧИКИ ---

@dp.message(Command("start"))
@dp.message(F.text == "🏠 Главная")
async def cmd_start(message: types.Message):
    logger.info(f"Пользователь {message.from_user.id} открыл главную.")
    await message.answer(
        WELCOME_TEXT,
        parse_mode="Markdown",
        reply_markup=get_main_keyboard()
    )

@dp.message(F.text == "📅 Сегодня")
@dp.message(Command("today"))
async def cmd_today(message: types.Message):
    status_msg = await message.answer("⏳ Читаю файлы...")
    text = get_today_events_text()
    await status_msg.delete()
    await message.answer(text, parse_mode="Markdown", reply_markup=get_main_keyboard())

@dp.message(F.text == "🔄 Обновить")
@dp.message(Command("update"))
async def cmd_update_manual(message: types.Message):
    await run_batch_update(message)
    await message.answer("Меню:", reply_markup=get_main_keyboard())

@dp.message(lambda m: m.document)
async def handle_docs(message: types.Message):
    doc = message.document
    file_name = doc.file_name.lower()
    logger.info(f"📥 Получен файл: {doc.file_name}")
    
    target_name = None
    
    # 🆕 ДОБАВЛЕНА ПРОВЕРКА НА КОНСЕРВАТОРИЮ
    if any(k in file_name for k in ["угк", "консерватория", "ugk", "расписание залов"]):
        target_name = FILE_UGK_HALLS
    elif any(k in file_name for k in ["зал", "hall", "филармония"]):
        target_name = FILE_PH_HALLS
    elif any(k in file_name for k in ["хор", "график", "choir", "сх"]):
        target_name = FILE_PH_CHOIR
    elif any(k in file_name for k in ["ельцин", "роял", "piano", "заявка"]):
        target_name = FILE_EC_PIANO
    elif any(k in file_name for k in ["сезон", "season"]):
        target_name = FILE_PH_SEASON
    else:
        # Fallback
        if file_name.endswith(".pdf"): target_name = FILE_PH_HALLS
        elif file_name.endswith(".docx"): target_name = FILE_EC_PIANO
        elif file_name.endswith((".xls", ".xlsx")): target_name = FILE_UGK_HALLS # 🆕 Умный fallback для Excel
        
        await message.answer(f"🤔 Не понял тип '{doc.file_name}'. Сохраняю как '{target_name}'.")

    if target_name:
        file_path = DATA_DIR / target_name
        await bot.download(doc, destination=file_path)
        logger.info(f"💾 Сохранено: {file_path}")
        
        await message.answer(f"✅ Файл `{target_name}` принят. Жду ещё {BATCH_DELAY} сек...", parse_mode="Markdown")
        schedule_batch_update(message)

# --- ЗАПУСК ---

async def main():
    logger.info(f"🤖 Бот Kairos запущен (Batch delay: {BATCH_DELAY}s)...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
