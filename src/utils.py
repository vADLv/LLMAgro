import pandas as pd
from datetime import datetime

def md_table_to_df(md_table: str) -> pd.DataFrame:
    if md_table ==-1:
        return pd.DataFrame()
    
    """Парсит текстовую таблицу работ в df"""
    lines = [line.strip() for line in md_table.split('\n') 
             if line.strip() and '---' not in line 
             and not line.startswith('Итоговая таблица') 
             and not line.startswith('Количество найденных операций')]
    
    headers = [col.strip() for col in lines[0].split('|')[1:-1]]
    
    data = []
    for line in lines[1:]:
        row = [cell.strip() if cell.strip() else None for cell in line.split('|')[1:-1]]
        data.append(row)
    
    df = pd.DataFrame(data, columns=headers).dropna(how='all')
    
    # Обработка числовых колонок
    numeric_cols = ['Уверенность распознавания', 'За день, га', 'С начала операции, га', 'Вал за день, ц', 'Вал с начала, ц']
    for col in numeric_cols:
        if col in df.columns:
            # Сначала заменяем None на NaN, затем обрабатываем строки
            df[col] = pd.to_numeric(
                df[col].replace([None, ''], pd.NA).str.replace(',', '.'), 
                errors='coerce'
            )
    
    # Обработка дат
    if 'Дата' in df.columns:
        df['Дата'] = pd.to_datetime(df['Дата'],dayfirst=False, errors='coerce')
        df['Дата'] = df['Дата'].fillna(pd.to_datetime(datetime.now().date()))

    if pd.to_datetime(df['Дата'].values[0]) > datetime.now():
        df['Дата'] = pd.to_datetime(df['Дата']) - pd.DateOffset(years=1)
    
    # Уверенность переносим в конец
    col_a = df.pop('Уверенность распознавания')
    df['Уверенность распознавания'] = col_a
    return df