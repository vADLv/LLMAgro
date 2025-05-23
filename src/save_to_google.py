import pandas as pd
import asyncio

import gspread_asyncio
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from datetime import datetime
import pytz
import os

from utils import md_table_to_df


# Константы
SRC_DIR = os.path.dirname(os.path.abspath(__file__))
# Файл для сервиcного аккаунта
SERVICE_ACCOUNT_FILE = f'{SRC_DIR}/progressagroproject-9dfb76fd1abc.json'
FOLDER_ID = '1-HxY9mFeOLLZ36h6t30nPBXmbOhNwcza'

SCOPES = ['https://www.googleapis.com/auth/spreadsheets',
          'https://www.googleapis.com/auth/drive']

# Доступ к почте
PERMISSION = {
    'type': 'user',
    'role': 'writer',
    'emailAddress': 's.sobolefff@gmail.com'
}

# Получение полномочий 
def get_creds():
    return Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE,
        scopes=SCOPES
    )

# Создане клиента Google Drive API
drive_service = build('drive', 'v3', credentials=get_creds())
agcm = gspread_asyncio.AsyncioGspreadClientManager(get_creds)


async def apply_conditional_formatting(report_name):
    """Условное форматирование"""
    client = await agcm.authorize()
    spreadsheet = await client.open(report_name)
    worksheet = await spreadsheet.get_worksheet(0)
    # Формируем правило условного форматирования
    request = {
        "requests": [{
            "addConditionalFormatRule": {
                "rule": {
                    "ranges": [{
                        "sheetId": worksheet.id,
                        "startRowIndex": 1,  # Строки 2-1000
                        "endRowIndex": 1000,
                        "startColumnIndex": 0,  # Колонки A-Z
                        "endColumnIndex": 26
                    }],
                    "booleanRule": {
                        "condition": {
                            "type": "CUSTOM_FORMULA",
                            "values": [{"userEnteredValue": "=AND($I2<8, $I2<>\"\")"}]
                        },
                        "format": {
                            "backgroundColor": {"red": 0.99, "green": 0.98, "blue": 0.8}  # Желтый
                        }
                    }
                },
                "index": 0
            }
        }]
    }
    
    await spreadsheet.batch_update(request)


async def save_json_to_folder(file_path):
    """Сохранение JSON-файла в папку"""
    # Названиe файла
    file_name = os.path.basename(file_path)
    # Метаданные
    file_metadata = {
        'name': file_name,
        'parents': [FOLDER_ID],
        'description': 'Сообщение с отчётом о проделанной работе.',
        'appProperties': { # Обход фильтрации
            'contentType': 'official_report', 
            'isVerified': 'true',
            'autoGenerated': 'false'
            }
    }
    # Подготовка файлов к загрузке в папку
    media = MediaFileUpload(file_path,
                            mimetype='text/plain',
                            resumable=True)
    
    # Загрузка файла в папку
    file = await asyncio.to_thread(
        lambda: drive_service.files().create(body=file_metadata,
            media_body=media,
            fields='id, webViewLink'
        ).execute())
    
    return file.get('webViewLink')


async def save_to_gsheet(df: pd.DataFrame, message_file_path) -> list:
    """Сохраняет DataFrame в Google Sheets с ежедневными файлами"""
    if df.empty:
        print("Нет данных для сохранения")
        return ""

    try:
        client = await agcm.authorize()
        # Создание имени файла
        df['Дата'] = df['Дата'].dt.strftime('%d-%m-%Y')
        report_name = f"{df['Дата'].values[0]}_ЗИП файл"

        # Запись сообщения
        file_url = await save_json_to_folder(message_file_path)

        # Добавление поля с кликабельной ссылкой
        df["Ссылка"] = f'=HYPERLINK("{file_url}", "Сообщение")'

        # Поиск или создание таблицы
        try:
            is_new = False
            spreadsheet = await client.open(report_name)
            worksheet = await spreadsheet.get_worksheet(0)
            
            # Дополнительная проверка, что файл не в корзине
            file_metadata = await asyncio.to_thread(
                lambda: drive_service.files().get(
                    fileId=spreadsheet.id,
                    fields='parents'
                ).execute()
            )
            
            if FOLDER_ID not in file_metadata['parents']:
                await asyncio.to_thread(
                    lambda: drive_service.files().delete(fileId=spreadsheet.id).execute()
                )
                # Если файл уже не в папке (удален или перемещен) - удаляем полностью и создаем новый
                raise Exception("Файл не найден")

        except:
            is_new = True
            spreadsheet = await client.create(report_name)

            await asyncio.to_thread(
                lambda: drive_service.files().update(
                    fileId=spreadsheet.id,
                    addParents=FOLDER_ID,
                    removeParents="root"
                ).execute()
            )
            
            worksheet = await spreadsheet.get_worksheet(0)
            await apply_conditional_formatting(report_name)
            print(f"Создан новый отчет: {report_name}")

        # Подготовка данных
        df = df.fillna('')
        
        
        # Формируем данные для загрузки
        if is_new or not (await worksheet.get_all_values()):
            # Список заголовков
            data_to_upload = [df.columns.tolist()]
            # Добавляем строки данных
            data_to_upload.extend(df.values.tolist())
            await worksheet.update(data_to_upload, value_input_option='USER_ENTERED')
            await worksheet.format("A1:Z1", {"textFormat": {"bold": True}})

        else:
            # Для существующей таблицы - только данные
            await worksheet.append_rows(df.values.tolist(), value_input_option='USER_ENTERED')

        await worksheet.columns_auto_resize(0, len(df.columns)-1)
        
        url = f"https://docs.google.com/spreadsheets/d/{spreadsheet.id}"

        print(f"Данные сохранены в {report_name}")
        print(f"Сылка на JSON-файл - {file_url}")
        print(f"Сылка на таблицу - {url}")
        return [url, report_name]
        
    except Exception as e:
        print(f"Ошибка: {str(e)}")
        return ''
    

if __name__ == "__main__":
    data = """Итоговая таблица: 

| Дата       | Подразделение | Операция                  | Культура                   | За день, га | С начала операции, га | Вал за день, ц | Вал с начала, ц |
|------------|----------------|---------------------------|----------------------------|-------------|------------------------|----------------|------------------|
| 04/13/2025 | Восход         | Сев                       | Кукуруза кормовая          | 24          | 252                    |                |                  |
| 04/13/2025 | Восход         | Предпосевная культивация  | Кукуруза кормовая          | 94          | 490                    |                |                  |
| 04/13/2025 | Восход         | Подкормка                 | Рапс озимый                | 152         |                        |                |                  |
| 04/13/2025 | Восход         | Подкормка                 | Овес                       | 97          |                        |                |                  |
| 04/13/2025 | Восход         | Боронование довсходовое   | Подсолнечник товарный      | 524         |                        |                |                  |

Количество найденных операций: 5."""

    print('--------------------------')
