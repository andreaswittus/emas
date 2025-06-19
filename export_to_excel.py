import sqlite3
import pandas as pd

db_path = "/Users/andreaskaastrup/Master thesis repository/emas/data/etl/database.db"
table_name = "email_testset_logs"
excel_path = "/Users/andreaskaastrup/Library/CloudStorage/OneDrive-Aarhusuniversitet/Speciale/Speciale/data/email_testset_logs.xlsx"

with sqlite3.connect(db_path) as conn:
    df = pd.read_sql_query(f"SELECT * FROM {table_name}", conn)

df.to_excel(excel_path, index=False)
print(f"Exported to {excel_path}")
