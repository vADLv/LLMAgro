import pandas as pd

def md_to_df(raw_table):
    lines = raw_table.strip().split('\n')
    headers = [col.strip() for col in lines[0].split('|')[1:-1]]

    data = []
    for line in lines[2:]:
        row = [cell.strip() for cell in line.split('|')[1:-1]]
        data.append(row)
    return pd.DataFrame(data, columns=headers).dropna(how='all')