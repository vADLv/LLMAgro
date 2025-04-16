import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from datetime import datetime
import pytz
import os
from utils import md_table_to_df


# Файл для сервиcного аккаунта
SRC_DIR = os.path.dirname(os.path.abspath(__file__))
SERVICE_ACCOUNT_FILE = f'{SRC_DIR}/progressagroproject-9dfb76fd1abc.json'
FOLDER_ID = '1EEbdC6WDtSpy68pmNLHAeU4d7Ca01MdK'

SCOPES = ['https://www.googleapis.com/auth/spreadsheets',
          'https://www.googleapis.com/auth/drive']

# Аутентификация
creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
client = gspread.authorize(creds)
drive_service = build('drive', 'v3', credentials=creds)

# Доступ к почте
PERMISSION = {
    'type': 'user',
    'role': 'writer',
    'emailAddress': 's.sobolefff@gmail.com'
}

def save_json_to_folder(file_path):
    file_name = os.path.basename(file_path)
    file_metadata = {
        'name': file_name,
        'parents': [FOLDER_ID],
        'description': 'Сообщение с отчётом о проделанной работе.',
        'appProperties': { # Обход фильтрации
            'contentType': 'official_report', 
            'isVerified': 'true'
            }
    }

    media = MediaFileUpload(file_path,
                            mimetype='application/json',
                            resumable=True)
    
    file = drive_service.files().create(body=file_metadata,
                                 media_body=media,
                                 fields='id, webViewLink').execute()
    
    drive_service.permissions().create(
        fileId=file.get('id'),
        body=PERMISSION,
        sendNotificationEmail=False
    ).execute()
    
    return file.get('webViewLink')


# TODO переписать под async (gspread_asyncio)
def save_to_gsheet(df: pd.DataFrame, message_file_path) -> list:
    """Сохраняет DataFrame в Google Sheets с ежедневными файлами"""
    if df.empty:
        print("Нет данных для сохранения")
        return ""

    try:
        # Создание имени файла
        msk_tz = pytz.timezone('Europe/Moscow')
        today_str = datetime.now(msk_tz).strftime('%d.%m.%y')
        report_name = f"Отчет_{today_str}"
        
        # Поиск или создание таблицы
        try:
            spreadsheet = client.open(report_name)
            worksheet = spreadsheet.get_worksheet(0)
            is_new = False
        except gspread.SpreadsheetNotFound:
            spreadsheet = client.create(report_name)
            drive_service.files().update(fileId=spreadsheet.id,
                                         addParents=FOLDER_ID,
                                         removeParents='root').execute()
            worksheet = spreadsheet.get_worksheet(0)
            print(f"Создан новый отчет: {report_name}")
            is_new = True
        
        # Подготовка данных
        df = df.fillna('')
        
        df['Дата'] = df['Дата'].dt.strftime('%Y-%m-%d')
        # Формируем данные для загрузки
        if is_new or not worksheet.get_all_values():
            data_to_upload = [df.columns.tolist()]  # Список заголовков
            data_to_upload.extend(df.values.tolist())  # Добавляем строки данных
            worksheet.update(data_to_upload, value_input_option='USER_ENTERED')
            worksheet.format("A1:Z1", {"textFormat": {"bold": True}})
        else:
            # Для существующей таблицы - только данные
            worksheet.append_rows(df.values.tolist(), value_input_option='USER_ENTERED')

        worksheet.columns_auto_resize(0, len(df.columns)-1)
        
        url = f"https://docs.google.com/spreadsheets/d/{spreadsheet.id}"

        # Выдача прав
        drive_service.permissions().create(
            fileId=spreadsheet.id,
            body=PERMISSION,
            sendNotificationEmail=False
        ).execute()

        # Запись сообщения
        message_url = save_json_to_folder(message_file_path)

        print(f"Данные сохранены в {report_name}")
        print(f"Сылка на JSON-файл - {message_url}")
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
    
    
    df = md_table_to_df(data)
    print(df)
    print('--------------------------')
