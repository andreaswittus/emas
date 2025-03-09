import os
import sqlite3
import pandas as pd

def _database_path() -> str:
    script_rel_path = os.path.dirname(__file__)
    return f"{script_rel_path}/../database.db"

def read_sql_table(table_name: str) -> pd.DataFrame:
    return pd.read_sql(
        sql=f"SELECT * FROM {table_name}", con=sqlite3.connect(_database_path())
    )

def upsert_df_to_sql_table(table_name: str, df: pd.DataFrame) -> None:
    with sqlite3.connect(_database_path()) as con:
        cur = con.cursor()
        cur.execute(f"CREATE TABLE IF NOT EXISTS {table_name} (col)")
        con.commit()
    df_sql = read_sql_table(table_name)

    number_of_rows_in_sql = df_sql.shape[0]

    if number_of_rows_in_sql > 0:
        df_to_write = pd.concat(
            [df, df_sql],
            ignore_index=True,
        ).drop_duplicates()
    else:
        df_to_write = df

    if df_to_write.shape[0]>0:

        df_to_write.to_sql(
            name=table_name,
            con=sqlite3.connect(_database_path()),
            if_exists="append",
            index=False,
        )

    else:
        print("No rows to write")