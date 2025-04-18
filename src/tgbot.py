import json
import os
import re
from datetime import datetime, date, timedelta
from dotenv import load_dotenv
from collections import defaultdict
import pytz

from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters
from telegram.constants import ParseMode

from llm import LLM
from utils import md_table_to_df
from save_to_google import save_to_gsheet
import prompts

load_dotenv()

# Константы
SAVE_FOLDER = "./data/messages"
HAS_DIGITS_REGEX = re.compile(r'\d')
COUNTER_FILE = os.path.join(SAVE_FOLDER, "message_counters.json")
MOSCOW_TZ = pytz.timezone('Europe/Moscow')  # Московский часовой пояс
LLM = LLM()

# Глобальные переменные
user_message_count = defaultdict(int)  # Счетчик сообщений по user_id
current_date = date.today()  # Текущая дата для проверки смены дня

def ensure_save_folder_exists():
    """Создает папку для сохранения, если её нет."""
    os.makedirs(SAVE_FOLDER, exist_ok=True)

def load_counters():
    """Загружает счетчики сообщений из файла."""
    global user_message_count, current_date
    
    # Если файла счетчиков нет - просто выходим
    if not os.path.exists(COUNTER_FILE):
        return
        
    # Загружаем данные из файла
    with open(COUNTER_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
        saved_date = date.fromisoformat(data["date"])
        
        # Если дата в файле совпадает с текущей - загружаем счетчики
        if saved_date == get_moscow_date():
            # Приводим ключи к строковому формату для единообразия
            user_message_count = defaultdict(int, {str(k): v for k, v in data["counters"].items()})

def save_counters():
    """Сохраняет счетчики сообщений в файл."""
    with open(COUNTER_FILE, "w", encoding="utf-8") as f:
        json.dump({
            "date": get_moscow_date().isoformat(),  # Текущая дата
            "counters": dict(user_message_count)  # Счетчики сообщений
        }, f, ensure_ascii=False, indent=2)

def get_moscow_date() -> date:
    """Возвращает текущую дату в московском часовом поясе."""
    return datetime.now(MOSCOW_TZ).date()

def check_date_change():
    """Проверяет смену дня и сбрасывает счетчики при необходимости."""
    global current_date, user_message_count
    
    moscow_date = get_moscow_date()
    if moscow_date != current_date:  # Если дата изменилась
        current_date = moscow_date  # Обновляем текущую дату
        user_message_count = defaultdict(int)  # Сбрасываем счетчики
        save_counters()  # Сохраняем пустые счетчики

def extract_sender_info(user) -> dict:
    """Извлекает информацию об отправителе."""
    return {
        "id": getattr(user, 'id', 0),  # ID с fallback на 0
        "first_name": getattr(user, 'first_name', ''),  # Имя
        "last_name": getattr(user, 'last_name', ''),  # Фамилия
        "username": getattr(user, 'username', '')  # Юзернейм
    }

def generate_filename(sender_info: dict, message_date: datetime) -> str:
    """Генерирует имя файла для сохранения сообщения."""
    load_counters()  # Загружаем актуальные счетчики
    check_date_change()  # Проверяем смену дня
    
    # Конвертируем время в московский часовой пояс
    if message_date.tzinfo is None:
        message_date = pytz.utc.localize(message_date)
    moscow_time = message_date.astimezone(MOSCOW_TZ)
    
    # Увеличиваем счетчик сообщений для этого пользователя
    user_message_count[str(sender_info["id"])] += 1
    save_counters()  # Сохраняем обновленные счетчики
    
    # Формируем строку даты в нужном формате
    date_str = moscow_time.strftime("%M%H%d%m%Y")
    
    # Очищаем имя отправителя от недопустимых символов
    sender_name = sender_info["first_name"] or sender_info["username"] or "Unknown"
    sender_name_clean = re.sub(r'[\\/*?:"<>| ]', "_", sender_name)
    
    # Формат имени файла: Имя_Счетчик_ДатаВремя.json
    return f"{sender_name_clean}_{user_message_count[str(sender_info['id'])]}_{date_str}.json"

async def save_message_to_file(message):
    """Сохраняет сообщение в файл и возвращает структурированные данные."""
    # Пропускаем сообщения без цифр (фильтрация нерелевантных сообщений)
    text = message.text or message.caption or ""
    if not HAS_DIGITS_REGEX.search(text):
        return '', ''

    # Извлекаем информацию об отправителе
    sender_info = extract_sender_info(message)
    if not sender_info:
        return '', ''

    # Определяем настоящего отправителя (для пересланных сообщений)
    if message.forward_origin:  # Переслано от пользователя
        user = message.forward_origin.sender_user
    else:  # Обычное сообщение
        user = message.from_user
    
    # Генерируем уникальное имя файла
    sender_info = extract_sender_info(user)
    filename = generate_filename(sender_info, message.date)
    filepath = os.path.join(SAVE_FOLDER, filename)

    # Нормализация времени (приведение к московскому часовому поясу)
    message_time = message.date
    if message_time.tzinfo is None:
        message_time = pytz.utc.localize(message_time)
    moscow_time = message_time.astimezone(MOSCOW_TZ)

    # Формируем структурированные данные для сохранения
    data = {
        "date": moscow_time.isoformat(),  # Локальное время (MSK)
        "date_utc": message_time.astimezone(pytz.utc).isoformat(),  # UTC время
        "tg_message_id": message.message_id,  # ID сообщения в Telegram
        "our_message_id": user_message_count[str(sender_info["id"])],  # Наш внутренний счетчик
        "sender": sender_info,  # Информация об отправителе
        "reply_to_message_id": message.reply_to_message.message_id if message.reply_to_message else None,
        "raw_text": text,  # Исходный текст сообщения
    }

    # Сохраняем данные в JSON файл
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    
    return data, filepath

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик входящих сообщений."""
    message = update.message
    if message is None:
        return
    
    # Сохраняем сообщение и получаем структурированные данные
    preprocessed_message, json_file = await save_message_to_file(message)
    
    if preprocessed_message:
        # Формируем промт для LLM
        params = {
            "raw_message": preprocessed_message,
        }
        filled_prompt = prompts.AGRO_PROMPT.format(**params)
        
        # Отправляем запрос к Yandex GPT
        md_table = await LLM.call_yandex_gpt(filled_prompt)
        
        if md_table != "-1":  # Если LLM вернула валидный результат
            # Конвертируем markdown таблицу в DataFrame
            df = md_table_to_df(md_table)

            # Сохраняем в Google Sheets
            report = await save_to_gsheet(df, json_file)

            # Отправляем ответ пользователю (если это личный чат)
            if message.chat.type == "private" and report:
                await update.message.reply_text(
                    f'Отчет <a href="{report[0]}">{report[1]}</a> сохранен',
                    parse_mode=ParseMode.HTML
                )

def main() -> None:
    """Основная функция инициализации бота."""
    # Инициализация системы
    ensure_save_folder_exists()  # Создаем папку для сохранения
    load_counters()  # Загружаем счетчики сообщений
    
    # Получаем токен бота из переменных окружения
    bot_token = os.getenv("TG_TOKEN")
    if not bot_token:
        raise ValueError("TG_TOKEN не найден в переменных окружения!")
    
    # Настройка и запуск бота
    app = ApplicationBuilder().token(bot_token) \
        .read_timeout(30) \
        .write_timeout(30) \
        .connect_timeout(30) \
        .pool_timeout(30) \
        .build()
    
    app.add_handler(MessageHandler(filters.ALL, handle_message))
    
    print("Бот запущен...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()