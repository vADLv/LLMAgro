import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from datetime import datetime
import pytz


data = """Итоговая таблица: 

| Дата       | Подразделение | Операция                  | Культура                   | За день, га | С начала операции, га | Вал за день, ц | Вал с начала, ц |
|------------|----------------|---------------------------|----------------------------|-------------|------------------------|----------------|------------------|
| 04/13/2025 | Восход         | Сев                       | Кукуруза кормовая          | 24          | 252                    |                |                  |
| 04/13/2025 | Восход         | Предпосевная культивация  | Кукуруза кормовая          | 94          | 490                    |                |                  |
| 04/13/2025 | Восход         | Подкормка                 | Рапс озимый                | 152         |                        |                |                  |
| 04/13/2025 | Восход         | Подкормка                 | Овес                       | 97          |                        |                |                  |
| 04/13/2025 | Восход         | Боронование довсходовое   | Подсолнечник товарный      | 524         |                        |                |                  |

Количество найденных операций: 5."""

# Файл для сервиcного аккаунта
SERVICE_ACCOUNT_FILE = 'progressagroproject-9dfb76fd1abc.json'

SCOPES = ['https://www.googleapis.com/auth/spreadsheets',
          'https://www.googleapis.com/auth/drive']

def parse_table(text: str) -> pd.DataFrame:
    """Парсит текстовую таблицу работ в df"""
    lines = [line.strip() for line in text.split('\n') 
             if line.strip() and '---' not in line 
             and not line.startswith('Итоговая таблица') 
             and not line.startswith('Количество найденных операций')]
    
    headers = [col.strip() for col in lines[0].split('|')[1:-1]]
    
    data = []
    for line in lines[1:]:
        row = [cell.strip() if cell.strip() else None for cell in line.split('|')[1:-1]]
        data.append(row)
    
    df = pd.DataFrame(data, columns=headers)
    
    # Обработка числовых колонок
    numeric_cols = ['За день, га', 'С начала операции, га', 'Вал за день, ц', 'Вал с начала, ц']
    for col in numeric_cols:
        if col in df.columns:
            # Сначала заменяем None на NaN, затем обрабатываем строки
            df[col] = pd.to_numeric(
                df[col].replace([None, ''], pd.NA).str.replace(',', '.'), 
                errors='coerce'
            )
    
    # Обработка дат
    if 'Дата' in df.columns:
        df['Дата'] = pd.to_datetime(df['Дата'], format='%m/%d/%Y', errors='coerce')
    
    return df



def save_to_gsheet(df: pd.DataFrame) -> str:
    """Сохраняет DataFrame в Google Sheets с ежедневными файлами"""
    if df.empty:
        print("Нет данных для сохранения")
        return ""

    try:
        # Аутентификация
        creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
        client = gspread.authorize(creds)
        
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
            worksheet = spreadsheet.get_worksheet(0)
            print(f"Создан новый отчет: {report_name}")
            is_new = True
        url = f"https://docs.google.com/spreadsheets/d/{spreadsheet.id}"
        
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

        # Доступ к почте
        drive_service = build('drive', 'v3', credentials=creds)

        permission = {
            'type': 'user',
            'role': 'writer',
            'emailAddress': 's.sobolefff@gmail.com'
        }

        drive_service.permissions().create(
            fileId=spreadsheet.id,
            body=permission,
            sendNotificationEmail=False
        ).execute()

        print(f"Данные сохранены в {report_name}")
        print(f"{url}")
        return url
        
    except Exception as e:
        print(f"Ошибка: {str(e)}")
        return ""
    

df = parse_table(data)
print(df)
print('--------------------------')
save_to_gsheet(df)
