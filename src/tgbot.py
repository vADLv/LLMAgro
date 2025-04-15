import json
import os
import re
from datetime import datetime, date, timedelta
from dotenv import load_dotenv
from collections import defaultdict
import pytz

from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters

load_dotenv()

# Константы
SAVE_FOLDER = "./data/messages"
HAS_DIGITS_REGEX = re.compile(r'\d')
COUNTER_FILE = os.path.join(SAVE_FOLDER, "message_counters.json")
MOSCOW_TZ = pytz.timezone('Europe/Moscow')  # Московский часовой пояс

# Глобальные переменные
user_message_count = defaultdict(int)
current_date = date.today()

def ensure_save_folder_exists():
    """Создает папку для сохранения, если её нет."""
    os.makedirs(SAVE_FOLDER, exist_ok=True)

def load_counters():
    """Загружает счетчики сообщений из файла."""
    global user_message_count, current_date
    
    if not os.path.exists(COUNTER_FILE):
        return
        
    with open(COUNTER_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
        saved_date = date.fromisoformat(data["date"])
        if saved_date == get_moscow_date():
            user_message_count = defaultdict(int, data["counters"])

def save_counters():
    """Сохраняет счетчики сообщений в файл."""
    with open(COUNTER_FILE, "w", encoding="utf-8") as f:
        json.dump({
            "date": get_moscow_date().isoformat(),
            "counters": dict(user_message_count)
        }, f, ensure_ascii=False, indent=2)

def get_moscow_time() -> datetime:
    """Возвращает текущее время в московском часовом поясе."""
    return datetime.now(MOSCOW_TZ)

def get_moscow_date() -> date:
    """Возвращает текущую дату в московском часовом поясе."""
    return get_moscow_time().date()

def check_date_change():
    """Проверяет смену дня и сбрасывает счетчики при необходимости."""
    global current_date, user_message_count
    
    moscow_date = get_moscow_date()
    if moscow_date != current_date:
        current_date = moscow_date
        user_message_count = defaultdict(int)
        save_counters()

def extract_sender_info(message) -> dict:
    """Извлекает информацию об отправителе."""
    if not message.from_user:
        return None
    
    return {
        "id": message.from_user.id,
        "first_name": message.from_user.first_name,
        "last_name": message.from_user.last_name,
        "username": message.from_user.username
    }

def generate_filename(sender_info: dict, message_date: datetime) -> str:
    """Генерирует имя файла."""
    check_date_change()
    
    # Конвертируем время сообщения в московский часовой пояс
    if message_date.tzinfo is None:
        message_date = pytz.utc.localize(message_date)
    moscow_time = message_date.astimezone(MOSCOW_TZ)
    
    # Инкрементируем счетчик сообщений
    user_message_count[sender_info["id"]] += 1
    save_counters()
    
    # Форматируем дату в московском часовом поясе
    date_str = moscow_time.strftime("%M%H%d%m%Y")
    
    # Очищаем имя отправителя
    sender_name = sender_info["first_name"] or sender_info["username"] or "Unknown"
    sender_name_clean = re.sub(r'[\\/*?:"<>| ]', "_", sender_name)
    
    return f"{sender_name_clean}_{user_message_count[sender_info['id']]}_{date_str}.json"

async def save_message_to_file(update: Update):
    message = update.message
    if message is None:
        return

    # Пропускаем сообщения без цифр
    text = message.text or message.caption or ""
    if not HAS_DIGITS_REGEX.search(text):
        return

    sender_info = extract_sender_info(message)
    if not sender_info:
        return

    # Генерируем имя файла
    filename = generate_filename(sender_info, message.date)
    filepath = os.path.join(SAVE_FOLDER, filename)

    # Конвертируем время сообщения в московский часовой пояс
    message_time = message.date
    if message_time.tzinfo is None:
        message_time = pytz.utc.localize(message_time)
    moscow_time = message_time.astimezone(MOSCOW_TZ)

    # Формируем данные для сохранения
    data = {
        "date": moscow_time.isoformat(),  # Сохраняем время в MSK
        "date_utc": message_time.astimezone(pytz.utc).isoformat(),  # Для время в UTC
        "tg_message_id": message.message_id,
        "our_message_id": user_message_count[sender_info["id"]],
        "sender": sender_info,
        "reply_to_message_id": message.reply_to_message.message_id if message.reply_to_message else None,
        "raw_text": text,
    }

    # Сохраняем в файл
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await save_message_to_file(update)

def main() -> None:
    ensure_save_folder_exists()
    load_counters()
    
    bot_token = os.getenv("TG_TOKEN")
    if not bot_token:
        raise ValueError("TG_TOKEN не найден в переменных окружения!")
    
    app = ApplicationBuilder().token(bot_token).build()
    app.add_handler(MessageHandler(filters.ALL, handle_message))
    
    print("Бот запущен...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()